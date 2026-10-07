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
| refs + neutral pass rate | +0.1 mean, median 16.4->13.6 (vs delta base) | adopted — **UNDER AUDIT (O-22, 2026-10-03): `neutral_pass_rate_l6`'s training NULL encodes a week-W blowout** |
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

> **UNDER AUDIT (O-22, 2026-10-03):** `qb_cpoe_l6` is joined by exact week from an event-only table (a QB has a row only if he threw about 15+ times that week), so its NULL encodes week-W information in training rows. If the six-season panel scored test weeks from training-table rows, this adoption's gain (tail weeks 18 -> 23) may come from an inactive/benched-QB oracle. The verdict stands provisionally until it is re-run on the fixed feature with a co-run control. See OPEN-DEFECTS O-22 and Addendum 121.

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

**Round 9 remainder (LEM / players-as-tokens):** the Large Event Model
is the most promising architecture idea yet for the sim — but it's a
GPU training project, and the honest gate is compute, not data. Shipped
tonight: scripts/lem_corpus.py tokenizes the full nflverse pbp
(1999-2025, ~1.25M plays; smoke-tested 143k plays / 855 games / 31k
composite vocab on 2023-25) into the SAME state space as the
possession-Markov engine, so the adoption bar is pre-registered:
held-out next-event log-loss vs the Markov transition model
(walk-forward, train <=2023, eval 2024-25), and only a winner earns
GAME_SIM_MODE=lem integration. nanoGPT ~10M params, one 24GB GPU,
hours-scale — first offseason/GPU-quota project. RisingBALLER-style
player embeddings fold into the same effort (player-conditioned LEM is
EventGPT exactly); the cheap proxy already in-system is archetype
clustering + the new causally-directed vacated features (Addendum 44),
which cover the same cold-start/role-change gap at feature scale.

## Addendum 45 (2026-08-03): market-implied distributions from alternate prop ladders — validated, endpoint shipped

Round 10's no-new-model idea, run on data already in house (prop_lines
holds DK alternate ladders 2023-25: 102k reception-yds rows / 141
distinct lines, 47k rush, 27k pass). Pairwise de-vig of Over/Under at
each alt line -> monotone implied P(over x) -> implied quantiles
(scripts/prop_implied_study.py; two bugs found en route: prices are
AMERICAN odds, and the naive first pass produced garbage curves that
the coverage check caught immediately).

Results (matched player-weeks vs panel actuals):
- The market's implied q90 arrives CALIBRATED out of the box: coverage
  0.921 recv / 0.917 rush vs target 0.90 — better than our LGB
  quantiles (0.863/0.843 on the same 2025 rows) — and beats us on rush
  pinball (5.87 vs 6.00), ties on recv (5.94 vs 5.95).
- **Disagreement is predictive BOTH directions** (the leverage
  finding): top-20% "model q90 >> market q90" rows outperform the
  market median by ~+6 yards on actuals; bottom-20% underperform it by
  ~-5. Neither source dominates -> the diff itself is the signal.

Shipped: inference/market_implied.py (tested de-vig/curve/quantile
module) + GET /api/market-tails (our p90-mean spread vs the market's
q90-q50 spread in DK pts, biggest gaps first) — a watchlist flag under
the ETR contract (never a silent model input). September follow-ups
queued: migrate market_ceilings' vig-naive ladder onto this module;
market-implied quantiles as EXTRA_FEATURES candidates (NULL pre-2023,
same precedent as FTN) for a replay arm.

**Round 10 remainder (cold-start pooling, ensemble weather, synthetic
data):**
- **Hierarchical Bayesian partial pooling: NULL on the slice it exists
  for.** On 1,316 cold-start 2025 rows (<=2 career games), explicit
  empirical-Bayes shrinkage (player -> pos x draft-round x depth group
  -> position) loses to the plain LGB (RMSE 6.103 vs 5.843); a 50/50
  blend is within noise (5.831) with worse MAE and bias. The GBM sees
  draft_round/depth_rank/is_cold_start and already pools implicitly.
  NumPyro build not justified; scripts/coldstart_bayes_study.py holds
  the harness if the 2026 rookie class reopens the question.
- **Ensemble weather (GenCast): right idea, staged on-ramp.** GenCast
  itself (TPU, ERA5 init pipeline) is an offseason project; the
  same-shaped cheap step is Open-Meteo's free ensemble endpoint (GFS/
  ECMWF members) — wire wind-speed SPREAD per stadium into the weather
  ingest in September and pass scenario weights into the sim
  (wind-sensitive draws already exist via temp/wind features).
  Historical ensemble forecasts aren't in house, so no backtest is
  possible tonight — live-data-gated, genuinely.
- **TabPFN synthetic data: queued behind the TabPFN projection
  experiment** — generation quality inherits from the same license-
  gated 2.5 model, and the stress-test use (rare regimes: snow games,
  backup QBs) needs a regime taxonomy first. Not data-gated, but
  effort-vs-evidence says it waits for the TabPFN main-line verdict.

## Addendum 46 (2026-08-04): research round 11 — kNN comps null, LLM env-forecast scaffolded, CV gated

- **Retrieval-augmented projection (kNN comps): null for adoption,
  third confirmation of the calibration pattern.** K=100 comps over
  standardized feature space (position-weighted, strictly prior
  seasons): RMSE 6.752 vs LGB 6.583, pinball90 1.408 vs 1.393 — LGB
  keeps the accuracy crown — but kNN's q90 coverage is exactly 0.900
  vs LGB's 0.871. Conformal (Add. 43), the betting market (Add. 45),
  and now comps all agree: OUR POINT-MODEL TAILS UNDER-COVER; every
  distribution-native method arrives calibrated. The sim already
  corrects in-draw (EMP_MARGINALS), so no adoption — but any DISPLAYED
  p90 (lineup cards, /api/market-tails) should eventually carry the
  conformal shift. Comps stay attractive as an explain-layer UI
  (scripts/knn_comps_study.py).
- **LLM game-environment forecasts (ForecastBench pattern): built for
  live validation, not backtested** — fuzzy-question backtests are
  contaminated (the model knows how 2025 games went). scripts/
  env_forecast.py runs the multi-stage pipeline (context -> sub-
  question forecasts -> critique -> final JSON: shootout_p, run_lean_p,
  pace) per game and logs to reports/env_forecasts/ for post-slate
  grading. Contract: watchlist context first; sim scenario weights only
  after a few graded live weeks show calibration.
- **CV on film: genuinely gated** — no footage pipeline in house and
  broadcast-video licensing is its own problem; nearest in-house proxy
  (NGS separation, snap shares) already feeds the models. Revisit only
  if a specific role-ambiguity (committee backfield) costs us a week.

**LEM v0 verdict (GPU run, 2026-08-04):** the composite-token
transformer (11.3M params, 49.5k vocab) LOST to the add-k bigram on
held-out 2024-25 next-event NLL — 8.192 vs 8.120, top-1 13.5% vs 16.8%
— exactly the failure the vocab math predicted (~9 training samples per
embedding). GPU quota turned out to exist (Cloud Run L4,
--no-gpu-zonal-redundancy, 1h task cap, ~$1/run), so the "offseason"
gate was imaginary; v1 with FACTORED tokens (7 small vocabs, summed
input embeddings, 7 output heads — the standard fix) launched the same
night. v0 checkpoint + metrics in gs://.../lem/.

**LEM v1 verdict (same night): FACTORED model BEATS the bigram on the
pre-registered bar** — held-out NLL/event 4.599 vs 8.120, with 1.9M
params and a 7-minute L4 run (~$0.15). Honest caveats logged with the
win: (a) a large share of the gap is the factorization itself — the
composite bigram hemorrhages probability on unseen exact transitions —
so the NEXT bar is a factored bigram (each factor conditioned on the
prior event); (b) on exact-match top-1 the bigram still edges v1
(16.8% vs 16.4%) by memorizing modal transitions — NLL is the metric
that matters for a generative sim, but the number is recorded. Road to
GAME_SIM_MODE=lem, in order: factored-bigram hurdle -> ROLLOUT REALISM
harness (generate full games; compare score distributions, drive
lengths, play counts vs held-out 2024-25 actuals; this is the gate
that counts) -> player-conditioning (EventGPT proper) -> replay A/B
vs the possession-Markov engine. Checkpoints/metrics in gs://.../lem/.

## Addendum 47 (2026-08-04): QF ADOPTED — N_QB_VARIANTS=4 + OWN_MODEL=fade become the defaults

Combo arms complete the exam: QF (QBVAR4+OWNFADE) 25 tails / median
14.6% (program best) / TWO >=237 weeks incl. a 254.6 max (program
high); QFC (QF + PUNT_MAX 3500 + no-game-stack) 24 — the extra pair
subtracts (and craters 2022 to 0/18); QBVAR4 alone 25 at median 15.0.
Adopted QF: equal-best tails, strictly better median, deeper ceiling.
Defaults now in code (engine N_QB_VARIANTS=4; replay OWN_MODEL=fade;
live fade upgraded to the trained ownership model with naive as a
LOGGED fallback only). "0"/"" restore the old behavior; the final
candidate panel (XFP/SCHED/VACC/MPG3/QD2) will run against the
post-adoption CONTROL. PMAX3500, NOGSTACK, RATEDW retire to the
registry as validated-neutral; VALUE2, WRBOOM1, TMW17, DIRK8 buried.

## Addendum 48 (2026-08-04): the four-reviewer pipeline audit — 17 verified findings, 3 commits of fixes

User-requested full audit of the sim pipeline and everything around it,
run as four parallel reviewers (selection engine, app/export, sim
pipeline, commit-range review) with every finding verified against the
code before fixing. Committed as 26cd477, f936052, 80f4051; every HIGH
carries a regression test or hard guard.

The five that mattered most:
1. **Thesis batch crashed the live endpoint** (UnboundLocalError on any
   feasible thesis — the block landed above its own seen-init) and its
   tags were clobbered. The unit test had passed because it tested the
   repair function, not the generation path — an end-to-end test now
   exercises the real path.
2. **/api/market-tails was dead on arrival** (guarded on 'p90'; the
   column is 'proj_p90') — the Addendum-45 feature returned [] forever,
   indistinguishable from "no props". Plus pass-yards priced 2.5x hot.
3. **xfp_l4 was structurally NULL at live inference** — exact-week join
   onto a pbp table with no upcoming-week rows; the replay A/B was real
   but adoption would have shipped silent train/serve skew (the exact
   class 023's header warns about). As-of join now.
4. **Late-swap locked rows could upload invalid slots** — sequential
   fill misaligned positions whenever the locked player sat in a
   different slot index in the new lineup; position-aware fill now, and
   genuinely un-arrangeable locks leave the row untouched.
5. **The prop-market merge could shift every draw index** on duplicate
   name-norm keys (each player scored with the NEXT player's draws)
   — dedup + hard length assert.
Also fixed: OWN_MODEL falsy-spelling footgun (own_mode()), TabPFN
live-parity gap + empty-cache fallback, NaN-game pseudo-correlation,
SHAPE_MIX=0 inversion, Lev% ~10x field-pct overstatement, lock-aware
churn assignment, DST rng decoupling, vacated CASE position source,
xfp offensive-TD-only rates.

Standing caveat: the in-flight final-panel arms (VACC/XFP/XSCHED) run
the PRE-fix SQL columns — replay signal stands, but any adoption
re-confirms on rebuilt tables (which the deploy requires anyway).
Ledger corrections: PMAX3500's exam null is PARTIALLY EXPLAINED — the
PUNT_MIN/PUNT_MAX levers only ever reached the ~2N lev candidates, not
the boom/qbvar/game batches, so the dose arms tested a weaker lever
than documented. Same for the cross-thesis repair regression and
_select_tail_qb_capped underfill (documented, low priority).

## Addendum 49 (2026-08-04): the final candidate panel — SCHED adopted, TabPFN validated on tails

Post-rebuild, post-QF-adoption build (CONTROL 18/107 on the new tables
— the rebuild law bit again: 23 -> 18 baseline shift, all arms co-run):

| Arm | Tails | Mean | Med% | Verdict |
|---|---|---|---|---|
| CONTROL | 18 | 176.0 | 15.1 | — |
| **SCHED** (net_rest_diff + body_clock_hour) | **24 (+6)** | 178.4 | 14.4 | **ADOPTED** |
| **TABPFN** (TabPFN marginals) | **24 (+6)** | 178.4 | **14.7** | validated; combo pending |
| XSCHED (XFP + SCHED) | 24 (+6) | 178.5 | 15.2 | = SCHED alone; XFP doesn't stack — **XFP part VOID, Addendum 121** |
| XFP | 20 (+2) | 179.4 | 14.8 | positive alone; stays candidate — **VOID: leaked feature, see Addendum 121 (2026-10-03)** |
| QD2 (MAP-Elites archive) | 18 (0) | 175.7 | 14.8 | validated-neutral |
| VACC (causal vacated capture) | 13 (−5) | 177.4 | 14.8 | REJECTED |
| MPG3 | vacuous | — | — | cap 3 < mandatory stack shape; MPG4 running |

SCHED is in NUMERIC_FEATURES (the XSCHED arm proves the exact adopted
model via sorted columns). TabPFN's +6 with the panel-best median
converts Addendum 43's calibration win into a TAIL win — the marginal
shapes matter where it pays. The SCHED+TABPFN stack arm (STPFN) decides
whether both ship as defaults; TabPFN live adoption additionally needs
the weekly projection-cache GPU job (built: tabpfn-gen; ~$0.05/wk) and
falls back to empirical marginals when the cache is missing (audit
round 3). VACC's -5 despite t>10 causal evidence is the program's
cleanest "true fact ≠ good feature" exhibit; the event-study finding
stands as scouting knowledge (Addendum 44).

**MPG4 verdict (the corrected MAX_PER_GAME dose):** 20 tails (+2) but
mean 175.7 and median 15.2 both WORSE than control — noise-band mixed,
not adoption-grade next to the clean +6s. Closes the winners-
concentration question the diffusion pitch raised: our 4.6-per-game
concentration vs winners' 2.96 is real but capping at 4 (the largest
dose compatible with the mandatory stack) doesn't buy tails — the
concentration gap is a symptom of our stack construction, not an
independent leak. MAX_PER_GAME retires to the registry as
tested-neutral; MPG3 recorded as infeasible-vacuous (cap < stack shape,
caught only because the audit taught us to look for vacuous arms).

## Addendum 50 (2026-08-04): STPFN — TabPFN marginals ADOPTED default-on; the stack verdict

SCHED+TabPFN together: 24 tails (equal to each alone — the +6s share a
mechanism budget, they don't add) but the BEST mean-best of the entire
panel (179.5 vs 178.4) at the tied-best median (14.7), deterministic
same-build comparison. Adopted: TABPFN_MARGINALS defaults to 1 —
per-player TabPFN quantile marginals over the possession-engine copula,
with automatic fallback to the EW empirical marginals when the
projection cache is absent (so live weeks degrade to the previous
default, never to raw). Operational contract: the tabpfn-gen GPU job
(~64s/season, ~$0.05) regenerates features.tabpfn_projections after
every feature-table rebuild and weekly in-season (runbook entry).
Final adopted stack of the program: EW + PUNT_BOOM=2 + QF
(N_QB_VARIANTS=4, OWN_MODEL=fade) + SCHED features + TabPFN marginals.

## Addendum 51 (2026-08-04): external model review (Gemini) — triage, fixes, and the LOSO consistency table

An independent Gemini review of the full ledger + complete source
(reports/external-review-package + code companion) returned findings;
each verified against code before acting. Its implementation
cross-checks all CONFIRMED our Addendum-48 fixes.

**1.1 Multiple comparisons (HIGH) — accepted, with evidence both ways.**
The reviewer's LOSO rule (adopt only if positive in >=4 of 6 seasons)
was computed retroactively for every current adoption:
| Adoption | +seasons | -seasons | LOSO 4-of-6 |
|---|---|---|---|
| SCHED | 4 | 0 | PASS |
| TABPFN | 4 | 1 | PASS |
| STPFN (shipped combo) | 4 | 0 | PASS |
| QF | 2 | 1 | **FAIL** |
QF stays adopted on cross-build replication (QBVAR4 +2 on a different
table build; Addendum 36's independent qualifier panel) plus
equal-tails/best-median — but it is now FLAGGED as the weakest adoption
and gets re-judged against real September standings at the qualifier
recalibration. LOSO >=4-of-6 (with no more than 1 negative) is ADOPTED
as a prospective validation law for future single-build adoptions.

**1.2 Silent TabPFN fallback (HIGH) — accepted, fixed.** /lineups now
returns model_health (cache probe per season/week) and the builder UI
shows a red warning when the sim used empirical-fallback marginals —
"never silently -6 tails on a Sunday."

**4.x Missing tests — all three added**: massive-lock late-swap stress
(6 locked cells, position-aware fill of the rest), DST variance guard
(gate-on rel-sd > 0.3), and the salary-lag threshold contract (pure
is_salary_lagged predicate mirroring the SQL; Gadsden-type promotion
must flag).

**1.3 Script-feedback pace multiplier — accepted as a lever to test**
(queued: SCRIPT_FEEDBACK env in game_sim, panel arm after the harvest).
**3.1 CQR live calibration** — queued for September (needs rolling live
accuracy; pairs with /api/accuracy). **3.2 consensus-divergence
feature** — queued as a candidate for the next panel round (market
data 2023+, FTN-style NULL precedent). **3.3 LEM "game flow"
attention** — PARTIAL REBUT: LEM v1's factored tokens already embed
score-differential and quarter (the sd/qtr factors); the real v2 items
are continuous embeddings and longer context, noted in the LEM road.

## Addendum 52 (2026-08-04): expansion-review verdicts, part 1 — showdown fade, and two vacuous-A/B catches

**SHOWDOWN_FADE (naive-ownership chalk fade for Captain Mode):** the
first two A/B attempts were VACUOUS and caught by the byte-identical
check — (1) stale :review image lacking the lever, (2) both arms on the
replay's MILP default while the lever (and live builds) run the sim
path. Law recorded: showdown A/Bs need SHOWDOWN_SIM=1 in BOTH arms +
an image probe. The real A/B (sim path, 43 slates 2025): capture-WASH —
84.8% vs 84.9% mean, 9/43 vs 8/43 slates ≥90%, median −1.1. Expected
shape: capture measures scoring accuracy, a fade buys leverage capture
can't see (no showdown field model exists). Verdict: costs ~nothing,
benefit unmeasurable pre-season → OFF by default, re-judged against
real showdown standings once September imports accrue.

## Addendum 53 (2026-08-04): the entries sweet-spot curve (3 seasons) and the LEM rollout gate

**Entries study complete** (2023-25, 54 week-slates, one 150-entry
sequential run per season; prefix-nested selection makes the first N
entries ~ the optimal N-entry portfolio; reports/entries_study/):
P(best-of-N ≥ 187 qualifier line) = 1.9% @N=1 → 16.7% @10 → 20.4% @15 →
31.5% @40 → 33.3% @50 → 44.4% @150. Marginal efficiency per entry:
~15-28/1000 through N≈10, ~4-7/1000 from 10-40, <1/1000 past 75. The
2025-only knee (~15) softens on three seasons — value keeps accruing to
~75 at reduced rate. Portfolio guidance stands: 30-50 entries per
contest across 2-4 contests beats one max-entry block (a week's entries
are identical across contests, so the benefit is multiple lines/fields,
not independent lotteries); never below ~15/contest (coverage cliff).
Full curve: sweet_spot_curve.csv.

**LEM rollout gate: FAILED 2/5** (400 generated games vs held-out
2024-25): TDs (4.72 vs 5.12 ✓borderline-pass rule) and turnovers pass;
punts over-generated (8.81 vs 7.19), FGs under (3.12 vs 4.03),
play-count sd too wide (15.9 vs 12.5). v1 stays OUT of the sim.
September v2 targets are now concrete: special-teams event calibration
+ drive-count variance, then re-gate — scripts/lem_train/rollout_eval.py
is the fixed yardstick.

## Addendum 54 (2026-08-04): the final harvest — and the honest cross-build picture

The shipping configuration (every adoption as a code default) on the
final tables (audit-fixed SQL) with the regenerated TabPFN cache:
**15/107 tail weeks** (7/1/2/1/1/3 by season), mean-best 175.1, median
14.1%, one ≥237 week (2019's 248.2 — its 193.0 mean-best is the best
2019 of the program). TabPFN mapping verified firing on every row; no
mechanical failure. This is a LOW order-luck draw, and it must be
recorded exactly that way:

| Table build | Same-build control | Adopted-stack result |
|---|---|---|
| A (exam, 2026-08-03) | 23 | QF 25 (+2) |
| B (candidate panel) | 18 | SCHED/TABPFN +6 each, STPFN 24 |
| C (final, fixed SQL) | (CONTROL2 pending) | **15** |

What bounces across builds is the ABSOLUTE level (±5 order luck per
rebuild, twice compounded here: new tables AND a regenerated marginal
cache). What replicated within every build is the RELATIVE gain of the
adopted levers. September's weekly retrains re-draw from this
distribution every Tuesday — the honest expectation is the
distribution's center with the adopted deltas, not any single draw,
and NO re-rolling of builds to chase a pretty number (that is
selecting on noise). The V2 panel's CONTROL2 runs the identical config
on the identical build and will confirm whether 15 is the build's
level or this run drew low within it.

## Addendum 55 (2026-08-04): the variance review (Gemini Pro) — determinism hardening adopted at the source

The targeted second review returned an expert-grade answer; triage:
**ACCEPTED (the cure, commit b0f7d9b):** (1) read-order determinism —
the panel load had NO ORDER BY (the reviewer said "before write"; in
BigQuery the fix belongs at READ time and in the feature SQL's windows
— corrected in implementation); (2) LightGBM deterministic=True +
force_row_wise=True + bin_construct_sample_cnt > N — all three
mechanisms verified real (thread-order histogram accumulation, the
row/col heuristic flip, subsampled bin boundaries); (3) the window
audit found two genuinely unkeyed ranks (017b referee had NO order at
all; 017g ranks tied target counts) — both now keyed. These change
numerics: the next rebuild panel validates them, and the definitive
cross-build test (rebuild twice, diff tables + replays byte-for-byte)
is a documented September experiment.
**DEFERRED with reasoning:** min_data_in_leaf 40→60-80 is a model
change wearing a determinism costume — it needs its own panel, queued.
**KEPT AS DATA DECIDES:** MODEL_ENSEMBLE — the reviewer's
variance-compression critique is right in general but partially
blunted here (TabPFN quantile mapping RESETS per-player marginal
widths after the mean ensemble, so compression affects ranks/levels,
not the simulated spread). The ENS3 arm is mid-flight; its verdict
stands alongside the source fix. Its "sample one member per draw"
suggestion is the better ensemble design if ensembling ever returns.
**CONFIRMED:** its attribution (model-side instigation, selection-side
amplification through the dense 180-194 near-miss band) matches
Addendum 36's own data — meaning source determinism suffices; no
selection-layer intervention needed.

## Addendum 56 (2026-08-04): MODEL_ENSEMBLE=3 ADOPTED — the largest gain of the program, born from the variance investigation

CONTROL2 (14/107) confirmed build C's low level; the ENS3 arm — three
LightGBM members per component, shuffled column orders + distinct
seeds, mean-averaged — scored **26/107** on the same build: +12, LOSO
+5/−1, best median (13.7%), and ABOVE every single-model build level
ever measured (23/18/15). Reading: averaging over the order-luck
dimension doesn't just stabilize the draw, it removes noise the greedy
selection layer was amplifying through the dense near-miss band — the
variance investigation's diagnostic chain (external review attribution
→ ensemble treatment → determinism hardening) converted the program's
biggest nuisance into its biggest win. The Gemini reviewer's
variance-compression objection is empirically refuted here (TabPFN
quantile mapping resets marginal spread after the mean average), while
its determinism-at-source fixes are ALSO adopted (b0f7d9b) — the two
treatments are complementary, not rivals. Registry persists ensembles
(member files + manifest, round-trip tested), so the September weekly
retrain carries K=3 with no operator action. TABCOMP (21, +7) is
superseded as the mean-layer treatment; it retires to the registry as
validated-positive-but-dominated. Shipping baseline: **26/107 —
ENS3's run IS the harvest of record** (identical config to the new
defaults, same tables).

## Addendum 57 (2026-08-05): V2 verdicts — and the ensemble changes what levers mean

Clean-build V2 panel (all arms one build, one image; CONTROL2 14
confirms build C's level):
| Arm | Tails | Δ | Verdict |
|---|---|---|---|
| SCRIPT2 (pace feedback) | 21 | +7 | see below — NOT adopted |
| ALTC2 (market ceiling room) | 19 | +5 (LOSO 3+/0−) | stack test running |
| DIVTILT2 | 16 | +2 | noise-band, retired |
| TABMEAN2 | 15 | +1 | null (marginals already carry TabPFN), retired |

**The lesson of the night, twice-taught:** single-model lever verdicts
do not survive the ensemble. SCRIPT2's +7 became **−2** stacked on
ENS3 (ENSSCRIPT 24 vs 26, LOSO 1+/3−) — the pace-feedback variance
that helped noisy single models is pure distortion once the ensemble
tames their noise. SCRIPT_FEEDBACK stays off. NEW VALIDATION LAW: with
MODEL_ENSEMBLE adopted, every lever verdict must come from (or be
confirmed on) an ensemble-based arm — pre-ensemble arms measure a
model that no longer ships. ALTC2's +5 gets the same stack test
(ENSALTC) before any adoption; the rookie-widen arm (RWIDEN) runs on
the current chain likewise. Also recorded: V1 of this panel was
destroyed by a mid-panel rebuild (my sequencing error) and its file
deleted at Erich's direction — V2 is the only citable version.

**ENSALTC verdict (2026-08-05): ALT_CEIL retired for good.** 22 vs
ENS3's 26 (0+/2− LOSO) — the second lever whose single-model gain
(+5) inverted under the ensemble (−4). The pattern is now law twice
over: the ensemble removes the noise these levers were unknowingly
harvesting. ALT_CEIL's history is a complete arc — vacuous (never
plumbed), revived (audit), single-model-positive (V2), and finally
rejected on the shipping config — the graveyard's best-documented
burial. Only RWIDEN remains open (it runs ON the ensemble config, so
its verdict is directly citable).

**RWIDEN verdict (final open lever): 22 vs 26 — rejected, 1+/4−.**
Third and cleanest confirmation of the post-ensemble law: the rookie
q90 gap is real (0.888 measured), the fitted 1.07 correction restores
coverage exactly, and it still costs 4 tail weeks — marginal
calibration and portfolio tails are different objectives once the
ensemble owns the noise budget. ROOKIE_WIDEN retires to judgment-lever
status (fitted constant preserved for rookie-extreme slates).
**THE PROGRAM'S FINAL ADOPTION SET IS CLOSED**: EW shaping + PUNT_BOOM
+ QF + SCHED features + TabPFN marginals + MODEL_ENSEMBLE=3 — nothing
else survived the ensemble era. The seal sequence (final image, full
deploy, keyed-window rebuild, cache regen, HARVEST-FINAL) measures the
shipping baseline.

## Addendum 58 (2026-08-05): THE SEAL — HARVEST-FINAL 25/107, and the variance work passes its first cross-build test

The sealed image (every adoption a code default) on freshly rebuilt
tables (keyed windows, ordered reads, deterministic LightGBM) with a
regenerated marginal cache: **25/107 tail weeks** (5/1/3/4/7/5), mean-
best 179.7, median 14.1%. THE SEPTEMBER BASELINE.

The cross-build ledger, complete:
| Build | Config | Result |
|---|---|---|
| A (exam) | pre-ensemble control | 23 |
| B (candidate panel) | pre-ensemble control | 18 |
| C (final-1) | pre-ensemble control | 14-15 |
| C | ENS3 (adopted stack) | 26 |
| **D (sealed, hardened)** | **adopted stack** | **25** |

Pre-hardening, three rebuilds of the same single-model config spanned
23→14 (±5 band). The adopted stack crossed a rebuild 26→25. One data
point, not proof — the rebuild-twice protocol remains September's
experiment — but it is precisely the signature the ensemble+determinism
work predicted, and it means the weekly Tuesday retrains should hold
their level rather than lottery-draw it. App and all 14 jobs serve the
sealed image. The pre-season program is CLOSED: six adoptions, a
57-addenda evidence ledger, a graveyard where every burial has a cause
of death, and a baseline measured on the exact bits that will build
Erich's week-1 lineups.

## Addendum 59 (2026-08-05): the gap decomposition — where the missing points actually live

Erich: "the maxes still seem low." Quantified against 54 weeks of
perfect-hindsight optimals (skill-8 MILP on full-slate actuals + ~10
DST, scripts era; gap_decomposition.csv):

| Quantity | Value |
|---|---|
| Hindsight optimal, avg (max) | ~268 (297-321) |
| Real Milly winners, avg | ~237 = 88% of optimal (best of 150k entries) |
| Our best-of-40 / best-of-150 | 66% / 69% of optimal |
| **Optimal players ANYWHERE in our 150 entries** | **84%** (50/54 weeks have ≥6 of 8) |
| **Optimal players in our BEST entry** | **1.87 of 8** |

**The gap is ASSEMBLY, not identification.** We roster the right
players — then scatter them. (Confirms the harvest attribution's
"right stacks, wrong pieces" at scale.) Order-statistics honesty: a
150k field draws 1000x more combinations than our 150 entries; parity
alone predicts the winner beats our best by ~25-35 — our 45-55 deficit
says our per-entry tail engine is field-typical while our MEDIAN is
top-14% — we are consistently good, rarely THE one. Realistic target:
capture 69% -> ~75% (+12-15 pts on best-of-150).

**Structural findings vs optimal (and winners):**
- Optimal lineups are BARELY stacked: 1.65 players from the QB's team
  incl. QB; max-any-team 1.87. Winners ~2.5-3. Our MANDATORY QB+2+
  bring-back forces a 4-man block — more correlated than either. The
  stack minimum PREDATES the A/B era and was never dose-tested — arms
  QBS1 (STACK_QB_MIN=1) and QBS1NB (+no bring-back) launched on the
  sealed config vs HARVEST-FINAL 25.
- Salary: optimal full-equiv ≈ 49.2k -> our 49k floor is CORRECT, not
  binding. Punts: optimal carries 1.30 sub-$4k -> punt rule CORRECT.
- The 16% of optimal players we never rostered skew WR (34/69), mean
  salary $4.8k, mean actual 30.3 (Achane 54.3, Jennings 49.5) — the
  mid-cheap boom our mean-anchored candidates skip. Lever design
  (September): q99-wildcard injection — force the week's top-N
  TabPFN-q99 sub-$6k skill players into ≥1 candidate each (cache
  column already exists); assembly batch — per top boom-sim, solve
  restricted to that sim's top-12 scorers (attacks 1.87/8 directly).

## Addendum 60 (2026-08-05): the graveyard design review — which burials were of ideas, which of implementations

Erich's question — could a better-constructed version of each rejected
arm succeed — audited against the gap decomposition and the
post-ensemble law:

**Retests justified (arms queued on the sealed config):**
- VACC2: the causal capture features were ADDED alongside the raw
  team-vacated sums they derive from — collinear pairs degrade GBMs.
  Clean design: capture features REPLACE the raw ones (DROP_FEATURES).
- VALUE2E: the ≥2-cheap-skill rule matches optimal structure exactly
  (missed booms avg $4.8k; optimal carries multiple cheap pieces) and
  its −1 verdict is pre-ensemble = stale by law.
- MPG3-conditional: infeasible only because of the 4-man stack
  mandate; if QBS1 wins, retest as a combo.

**Burials that survive the autopsy:**
- ALT_CEIL / WRBOOM: failed as OBJECTIVE TILTS (distort every build);
  the same players' correct mechanism is CANDIDATE INJECTION (q99
  wildcards — designed, September). Mechanism rejected, target alive.
- ROOKIE_WIDEN: draw-wide was wrong; narrow redesign = rookie
  punt-valuation correction only (September).
- TABMEAN: dead by construction (marginals already carry the center).
- SCRIPT: clean ensemble-era negative; refined pace design only if
  September shows a shootout-miss pattern.
- TMW17, DIRK8, PSLOPE/PSTRICT/LOWSAL: no mechanism evidence surfaced
  by any later analysis; buried on merits.

## Addendum 61 (2026-08-05): model-technique audit, GPU verification, and the eval upgrade

**GPU artifacts verified sound, not just present**: marginal cache —
100% monotone ladders, zero nulls, stable ~10-pt q90−q50 spreads, all
six seasons. Component cache — actuals-correlations IMPROVE with
context size (targets r .545→.623, the ICL signature); TabPFN's
occasional negative counts (539 rows at the smallest 2019 context,
~0 later) are neutralized by the production clips at consumption.

**Technique audit**: every model uses a defensible technique; the real
gaps are UNTRIED TabPFN placements, ranked: (1) DST projections — the
stack's weakest model (trailing means) and a pure cache-pattern
experiment; (2) ownership vs the .727 booster; (3) the licensed v2.5
upgrade (Erich accepts at priorlabs.ai → TABPFN_TOKEN → regenerate
caches → one panel). Plus the best remaining ensemble idea:
**heterogeneous members** — the K=3 ensemble is all-LGBM; a mixed
family (LGBM + CatBoost + TabPFN-mean member) adds diversity that
seed/column shuffles cannot. All September arms.

**Eval strategy upgraded** (Erich: "would a better eval find problems
easier?" — yes, proven tonight): the tails metric is outcome-only;
every mechanism discovery of the last 24h came from ad-hoc analysis.
scripts/diagnose_portfolio.py now packages that battery (capture%,
pool-hit%, assembly-vs-random-null, pair co-occurrence, QB anchoring,
generator attribution) as a one-command standing diagnosis. New eval
rule: an arm that moves tails without moving ANY diagnostic is
suspected of winning on noise; an arm that moves a diagnostic without
moving tails is a mechanism lead worth a redesign.

## Addendum 62 (2026-08-05): the selection-ordering audit — coverage is real, ranking is decorative

Erich asked whether the selection process ITSELF had been analyzed.
The ordering had not — and it fails: across 54 weeks, entry #1 (the
sim's single highest-P(>=line) pick, crowned "strongest" in the UI)
lands at the 49th percentile of our own portfolio's realized scores —
a coin flip. Spearman(selection order, realized score) = +0.086
(mildly INVERTED); 187-clearers sit at median rank 68; the 81-150
bucket has the highest realized mean. What survives: the first-40
CONTAINS the weekly best 50% vs 27% uniform — the prefix has portfolio
breadth value while its internal order is noise. Formal statement:
tail-coverage selection is validated at the PORTFOLIO level (what
panels measure); the sim cannot rank its own entries because hero
status is decided by co-boom realizations it models only
approximately. Consequences: (a) UI relabeled honestly (entries are
co-equal shots); (b) PRE-REGISTERED PREDICTION: the in-flight PEAK10
arm doubles down on the discredited p_line ranking and should return
null — if it does, the diagnostic-eval rule caught a bad lever before
its panel; (c) trimming 150->N loses breadth, not "the best ones" —
consistent with the sweet-spot curve's shape.

## Addendum 63 (2026-08-05): the stack mandate survives its first test ever — decisively

QBS1 (STACK_QB_MIN=1): 17 vs HARVEST-FINAL 25 (0+/4−). QBS1NB (also
no bring-back): 17 (0+/5−). Both loosening doses lose ~a third of the
tails. The QB+2-catchers+bring-back mandate — adopted pre-A/B-era on
winner anatomy, and challenged tonight by the hindsight-optimal
structure (avg 1.65 QB-team players) — is validated at last, and the
apparent contradiction resolves the program's closing principle:
hindsight optimals are made of INDEPENDENT booms nobody can predict;
a strategy manufactures correlated ones. WHAT WON is not HOW TO HUNT.
The assembly finding (below-random 1.87/8) stands, but its remedy is
candidate injection and assembly batches (queued), NOT loosening the
correlation skeleton — that was just tested and bled. Remaining
in-flight: VACC2, VALUE2E, then NBOOM and PEAK10 (PEAK10 carries
Addendum 62's pre-registered null prediction).

## Addendum 64 (2026-08-05): the leaderboard-pool analysis — aggregate stratum done, per-entry stratum specced

Winner-level anatomy existed (Addenda 38+); the FIELD-level stratum is
now analyzed via the ownership aggregates (54 contest-weeks x top-60
owned): splitting weeks by the field's collective chalk performance,
our best-of-150 clears 187 in 60% of chalk-BUST weeks vs 40% of
chalk-WIN weeks (corr −0.11) — the fade construction is positioned
exactly as designed, paying differentially when the crowd fails
without collapsing when it succeeds. Field top-10 chalk hits the
top-10 scoreboard only ~2.7/10 in every regime — the crowd's ceiling
blindness is persistent, and it is the edge.

**Per-entry leaderboard stratum (top-N anatomy beyond the winner):
GENUINELY September-gated** — contest_entries populates only from
Erich's standings imports (machinery built, table empty). Specced for
the first 2-3 weeks of imports: top-1% vs top-10% vs median entries on
ownership-sum, stack shape, salary left, dupe counts, punt usage —
the question being whether NEAR-winners share the winner anatomy or
the winner is an outlier of a different process (changes whether we
target the top-1% shape or the winner shape).

## Addendum 65 (2026-08-05): the per-entry leaderboard stratum — found in-repo, analyzed, and the winner IS different

Erich was right: full per-entry standings existed in the
RTS-Little-Data-Bowl clone — 74 contests from 2021, up to 408k entries
each (FLEX-6 format; behavior universals transfer, construction rules
do not). 63 large contests, 19,507 stratified entries:

| Stratum | own-sum | min-own | duped% |
|---|---|---|---|
| winner | **235** | **11.9** | **85%** |
| top 0.05% | 245 | 13.7 | 97% |
| top 1% | 251 | 14.7 | 97% |
| top 10% | 254 | 15.3 | 97% |
| median | 250 | 14.3 | 95% |

**The September question is answered early: near-winners do NOT share
the winner's anatomy — the top-1% looks like the median on ownership;
only the WINNER is contrarian and unique.** Consequences: (a) target
the winner's shape (leverage + uniqueness), not the top-1% shape —
chasing the leaderboard's average anatomy optimizes for
almost-winning; (b) this independently validates the fade + uniqueness
construction from field data at scale; (c) re-run this exact analysis
on Erich's own September imports (classic format, his fields) to
calibrate the DOSE — the 2021 FLEX data fixes the direction, not the
magnitude. Also noted for the ledger: the winner-vs-leaderboard
uniqueness gap (3-5x) is the empirical justification for max_overlap
diversity in selection that the ordering audit (Add. 62) could not
supply.

**Redesign-arm verdicts (Addendum 60's retests, on the shipping
config vs HARVEST-FINAL 25):** VACC2 (capture features REPLACING the
raw vacated sums) 21 — the collinearity redesign did not rescue it;
the causal vacated family retires with idea AND implementation both
fairly tested. VALUE2E 26 (+1, LOSO 2+/1−) — inside the noise band,
fails the bar honestly; the cheap-skill mechanism is already carried
by the punt rule. Remaining in flight: NBOOM, PEAK10 (pre-registered
null), GREEN (the branch architecture comparison).

**Assembly-arm verdicts:** NBOOM (boom solves 40→100) 25 vs 25 —
exact null; the 40 saturate. PEAK10 21 vs 25 (0+/3−) — Addendum 62's
PRE-REGISTERED prediction confirmed and exceeded: reserving slots for
p_line-ranked picks costs breadth for a ranking that carries no
realized signal. The diagnostic-eval rule's first full catch:
designed on a discredited signal → predicted null → delivered
negative. Combined with the stack-mandate validation, the assembly
gap's remedy is now narrowed to ONE untested mechanism: the
architecture itself (GREEN, running last).

## Addendum 66 (2026-08-05): GREEN — the alternate architecture reaches parity on its first attempt

The greenfield-v1 branch (per-world argmax primary generator +
beat-the-Gumbel-extended-field-bar selection, sharing the validated
worlds engine): **27 vs HARVEST-FINAL's 25** — but +2 inside the noise
band, LOSO 2+/2−, and the incumbent keeps the better mean (179.7 vs
178.7), median (14.1 vs 14.6), and the only ≥237 week. NOT adopted.
The finding is nonetheless the day's most forward-looking: a v1
architecture reached PARITY with the 66-addenda incumbent in one
attempt, with none of its refinements. The branch survives as the
September iteration vehicle; its v2 backlog (from the greenfield doc,
not yet in v1): the field bar from REAL imported standings instead of
the sampled naive field; dupe-aware bar margins; hybrid generation
(world-argmax + the incumbent's diversity batch feeding ONE selection);
and the diagnostic battery run on its exports to see whether its
assembly overlap beats the incumbent's 1.87 — if it does, the
architecture wins on mechanism even at score parity, and iteration is
justified by the eval rule.

**THE LEDGER CLOSES HERE.** Final state: six adoptions (EW, PUNT_BOOM,
QF, SCHED, TabPFN marginals, MODEL_ENSEMBLE=3), baseline 25/107 sealed
and deployed, twelve challengers repelled on the final day, one
alternate architecture at parity on a branch, and every question that
can be answered without September data — answered.

## Addendum 67 (2026-08-05): the no-settling sweep — three "September" items tested tonight instead

Erich refused to settle; three deferred items got built and tested:
1. **Late-swap score alpha: NULL, measured honestly.** The unconstrained
   tease (+24 mean-best) was pure legality inflation; position-legal,
   salary-feasible q90-chasing nets +0.9 with flat P(187). The perfect-
   swap upper bound (+69, 100% of weeks ≥187) is hindsight-only —
   individuals remain unpredictable. What SURVIVES for September:
   late-swap's leverage/uniqueness value (post-lock ownership is
   REVEALED information the fade could exploit) — unmeasurable by
   score-capture pre-season, same epistemic class as the showdown
   fade. The churn-min pipeline already preserves the optionality.
2. **Q99_WILD** (ceiling-wildcard injection — the untested assembly
   mechanism; gsis plumbed after a vacuity near-miss): arm running.
3. **MODEL_ENSEMBLE_MIX** (heterogeneous third member, sklearn HistGB,
   replay-only until registry support): arm running.

## Addendum 68 (2026-08-05): review #3 triage — the objective-function review lands blows

The targeted review (objective + field model) returned four findings;
triage:
**F2 (Gumbel IID flaw): VERIFIED AND FIXED SAME HOUR.** Its exact
validation plan run on the 63 real 2021 contests: the analytic
extension over-scales the winning bar **4.26x** (16.8 vs the measured
3.9-pt true-max gap; empirical constant = 0.256 field-SD). GREEN v1
reached parity while chasing bars ~13 pts too high — the corrected
GREEN2 arm is running. If GREEN2 clears the incumbent decisively, the
architecture question reopens TONIGHT.
**F1 (fixed line optimizes near-winner anatomy): ACCEPTED as the
September strategic direction** — it synthesizes Add. 65 + GREEN
correctly. Not adopted overnight because the incumbent still holds
the measured profile edge; the reviewer's validation plan (judge
architectures on assembly + expected dollars, not line-clearing) is
now the standing rule for the architecture track.
**F3 (skeleton-resampler field model): the best architectural idea of
all three reviews** — resample real per-entry lineups as structural
skeletons, inject current players, validate the FIELD ITSELF with the
diagnostic battery. September build #1; 2021 FLEX skeletons are
direction-only (format mismatch), his classic imports are the
calibration data.
**F4 (split objectives per contest): ACCEPTED, partially pre-built** —
converges with the held SELECT_OBJ=dollars and the memory's
automation TODO. The 4-entry Milly slice genuinely cannot play
coverage (below the cliff); dollars/uniqueness objective for it, and
the rank<=seats objective for qualifiers once the field model (F3)
exists. Queued with the reviewer's exact validation design.

**Final lever verdicts:** HET (heterogeneous ensemble member) 21 vs 25
— the HistGB family subtracts; the homogeneous shuffle-ensemble is the
right design, retire. WILD (q99 ceiling injection) 23 vs 25 — the
LAST assembly mechanism nulls; the never-rostered booms weren't
flaggable ex-ante even at q99, the individuals-unpredictable law's
final word. The assembly gap's only remaining candidate is the
architecture itself: GREEN2 (empirically-corrected bar) and the M4
objective pair are the program's final two verdicts.

## Addendum 69 (2026-08-05): GREEN2 verdict — corrected architecture at parity; v1's edge was the bug

GREEN2 (per-world argmax + beat-the-bar selection with the EMPIRICAL
field-max extension 0.256·sd, review #3's fix): **24 vs incumbent 25**
(per-season deltas 0,0,-1,0,-1,+1; mean best 179.6 vs 179.7; median
percentile 13.7 vs 14.1). GREEN v1's 27 was scored WITH the 4.26x
over-scaled bar — correcting the bug removed the edge, i.e. the edge
WAS the bug (an over-tight bar behaves like an aggressive
ceiling-tilt). Score verdict: the alternate architecture is at exact
parity with the incumbent on its first two attempts, never ahead once
correct. Architecture question stays CLOSED for week 1; GREEN remains
the September vehicle for the skeleton-resampler field model (a real
modeled bar instead of a constant extension is precisely its missing
piece). Assembly-mechanism comparison (review #3 F1 standard) queued:
CONTROL-40e vs GREEN2-40e on 2025, diagnostic battery both —
mechanism-without-score would be a documented September lead, not an
adoption.

**M4LINE interim** (4-entry fixed-line slice, the Milly reality
check): 3/107 line-clears vs 25/107 at 40 entries — the coverage
cliff the reviewer predicted, measured. The pair verdict vs
M4DOLLAR (expected-dollars objective) decides week-1 Milly selection.

## Addendum 70 (2026-08-05): M4 pair verdict — dollars objective NULL at 4 entries; fixed line stands

Review #3 F4's exact experiment: 4-entry portfolios (the real Milly
slice), fixed-line selection (M4LINE) vs expected-dollars objective
(M4DOLLAR), six seasons. Result: **null with a lean to the incumbent**.
Tails identical (3/107 each — the coverage cliff measured); ROI season
wins 3-3 with the six-season totals dominated by two opposite-sign
single-week jackpots (noise); median percentile FAVORS the fixed line
(12.6 vs 14.0, better in 4/6 seasons). The reviewer's theory that
below-cliff portfolios should optimize simulated ROI directly does not
survive its own test. CAVEAT that keeps it honest: replay ROI is
scored against the naive marginal field model — the same field model
F3 indicts. Re-judge ONLY if/when the September skeleton-resampler
field model exists; until then SELECT_OBJ=dollars stays HELD and
week-1 Milly entries use the standard fixed-line selection (the 4
Milly entries = first 4 of the run, co-equal shots). Review #3 is now
fully adjudicated: F2 fixed (and the fix nulled GREEN's edge —
Addendum 69), F4 tested-null, F1/F3 September directions.

## Addendum 71 (2026-08-05): Review #4 triage — five arms launched, one claim refuted same-hour

Review #4 (the "wall" brief) returned 7 findings. Triage and action:

- **F1 (log-sum-exp selection — coverage's binary threshold scatters
  co-booms)**: the sharpest mechanistic hypothesis for the
  below-random assembly overlap anyone has produced. CODED
  (SELECT_LSE=<alpha> in select_tail_entries; greedy on
  sum_w log sum_S exp(alpha*(score-line)), still submodular). ARM: LSE
  alpha=0.08, 6 seasons. Falsification per reviewer: mean best must
  rise from 179.7 or assembly overlap past 2.51.
- **F2 (ceiling math)**: verified — Gaussian-tail EVT gives
  sqrt(ln40/ln150k) ~= 55% as the naive best-of-40 capture bound; we
  measure 69%, winners-with-150k-human-entries 88%. Their verdict
  stands: stop chasing capture, buy structure. Judgment recorded, not
  testable.
- **F4 (ownership barbell — winners reach contrarian sums via
  chalk+zero barbell, not smooth fade)**: CODED (OWN_BARBELL linear
  proxy: >=3 skill players <=5% own AND >=2 >=20%). ARM: BARBELL =
  OWN_BARBELL=1 + OWN_MODEL=off (reviewer's design: barbell REPLACES
  the fade).
- **F5 (4-entry concentration — one QB family, no coverage)**: CODED
  (M4_QBLOCK: pick the QB family maximizing P(any >= line)). ARM:
  M4QBLOCK at 4 entries vs M4LINE (3/107, median pct 12.55).
- **F6 (deletions — fade and punt mandate never re-tested
  post-ensemble)**: correct procedural point; both are pre-ensemble
  adoptions. NO CODE NEEDED. ARMS: NOFADE (OWN_MODEL=off), NOPUNT
  (PUNT_MIN=0 + PUNT_BOOM=0). Falsification: if 25 holds, delete.
- **F7 (pairwise co-ownership matrix — "you're flying blind into
  crowded stacks")**: MEASURED SAME-HOUR on the 74-contest archive
  and REFUTED there: median joint/product inflation of top-20 pairs =
  0.87 (mean 0.84, p90 1.08); only 0.3% of pairs exceed 1.5x, 20%
  are repelled <0.67x (cap/slot substitution); max chalk-pair
  inflation 1.7x (RB+own-DST, game pairs) — nowhere near the claimed
  2.4x. Independence errs mildly CONSERVATIVE in this archive.
  CAVEAT: showdown format — classic QB+WR stack inflation re-measured
  on September imports; the skeleton resampler encodes whatever the
  real number is automatically. Data: ~/nfl-panels/coownership_pairs.csv.
- **F3-adjacent ranking** (dup-penalty > skeleton bar > per-contest
  lines): noted for September; the dup-penalty needs the F7-style
  matrix from CLASSIC standings, which is exactly what September
  accrues.

Image :rev4 (levers + tests, commit 70d5173). Chains gated on the
assembly diagnostic and on image existence (stale-image law): panel
family LSE -> BARBELL; rev family NOFADE -> NOPUNT -> M4QBLOCK.

**Post-selection law (2026-08-05, operator insight):** generalizing
the post-ensemble law — verdicts don't transfer across a changed
downstream stage. All generation-lever graves predate the selection
objective now under test; if SELECT_LSE adopts, VALUE2E (26),
Q99_WILD (23), and N_BOOM (25) get re-judged under the new selector
before their burials are trusted (PEAK_SLICE stays buried — LSE
subsumes it). Queue + rationale: memory post-selection-retest-queue.

## Addendum 72 (2026-08-05): CORRECTION — Addendum 69's GREEN2 was VACUOUS; the corrected architecture was never measured

The assembly diagnostic returned byte-identical batteries for CONTROL
and "GREEN2" — the vacuity signature. Root cause: the GREEN2 panel
script (and the diag) passed GREEN2FIELD=1 but the branch gate reads
GREENFIELD. The lever never fired. Consequences, honestly:

- **Addendum 69 is WRONG.** "GREEN2 = 24" was the incumbent
  construction on a rebuilt image — its 24-vs-25 delta is cross-build
  noise. The claim "the corrected bar removed the edge / the edge was
  the bug" is unsupported.
- **GREEN v1's 27 stands** (panel_green.sh used GREENFIELD=1
  correctly). The architecture's only real datapoint is 27 vs 25 —
  WITH the over-scaled bar.
- The corrected-bar architecture (empirical 0.256·sd) is now ACTUALLY
  running: arm G2FIX, own job family (replay-g2-*), results
  ~/nfl-panels/g2fix_results.txt. Assembly diag redo
  (assembly_diag2.sh) re-gated to run last.
- Process note: the vacuity law caught this — but only because the
  diagnostic battery ran. A score-only readout (24, plausibly parity)
  sailed through. LAW STRENGTHENED: an arm whose lever lives on a
  BRANCH image must verify the env gate name against THAT branch's
  code (img-probe covers the image, not the spelling of the gate).

**Addendum 72 resolution — G2FIX (the real corrected-bar GREEN):
25/107, exact parity.** Per-season {2019:6, 2021:2, 2022:3, 2023:5,
2024:5, 2025:4} vs incumbent {5,1,3,4,7,5}: +3/-2 seasons, tails tied
25-25, mean best 179.9 vs 179.7, two >=237 weeks (248.8, 249.6). The
architecture verdict, now on honest data: per-world argmax +
empirical-bar selection EQUALS the incumbent everywhere except v1's
over-scaled-bar 27 (real, but within the +/-2-3 noise band and
mechanistically an accidental ceiling-tilt). Architecture stays
unadopted for week 1; the assembly-diag redo decides whether it
carries a MECHANISM lead into September. The GREEN backlog note in
september-operator-notes stands with G2FIX as the reference number.

## Addendum 73 (2026-08-05): LSE verdict — NULL by its own falsification; the assembly gap is generator-bounded

LSE (SELECT_LSE=0.08, review #4 F1): tails 25/107 (tie), mean best
179.3 vs 179.7 (did NOT rise), per-season {6,2,3,4,5,5} vs
{5,1,3,4,7,5}. Lever verifiably fired (means/medians/profiles all
moved; season maxes identical to control — the weekly best candidate
survives every selector, which is itself evidence selection was never
the binding stage). Per the reviewer's pre-registered criterion this
FALSIFIES the selection-defect hypothesis: the below-random assembly
overlap is a property of the CANDIDATE GENERATOR's noise (W2:
individuals unpredictable), not of coverage's binary threshold.
Retest chain voids automatically (LSE <= 25): the VALUE2E / Q99_WILD
/ N_BOOM graves stand. The wall's W1 is now closed as "not a defect"
— the remaining edge, per F2's verified math, is structural (field/
duplication), which is September's skeleton-resampler work.

## Addendum 74 (2026-08-05): LSE log mining — the portfolio out-tails its own Gaussian model by +7 weeks

Parsing all six LSE runs' entries-to-line tables (106 weeks): summing
the Gaussian-implied per-week P(clear 194 with 40 entries) predicts
17.9 clears; actual = 25. The +7 is NOT luck — the boom-solve entries
give the portfolio a heavy right tail the week's Gaussian fit (mu
~110-140, sd ~20-35) cannot represent. Implications: (a) tails are
manufactured by the boom generator (attribution agrees: 8/18 weekly
bests from 58% of pool), not by breadth; (b) all Gaussian-derived
difficulty numbers (N@237 medians ~1M, "6/18 reachable", reviewer
F2's EVT ceiling) are CONSERVATIVE for our portfolio specifically.
Also measured: clears are environment-gated (cleared weeks mu 131/sd
28.4 vs missed 122/22.9 — the slate booms, not the picks); best-scorer
selection rank median 20 = uniform, though rank<=10 holds 31% of
bests vs 25% uniform (faint, not actionable); 17 "reachable misses"
mostly low-sd weeks = the Gaussian overstating quiet-slate
reachability. Expected clears at 150 entries (Gaussian, conservative):
38.4 — the entries-count curve still has slope past 40, relevant to
contest-mix sizing.

**Addendum 74b — BARBELL verdict: 24/107, null-negative.** (OWN_BARBELL
=1 + OWN_MODEL=off, review #4 F4.) Mean best 178.4 vs 179.7; per-season
{4,2,3,3,7,5} vs {5,1,3,4,7,5}. The lever fired (portfolio chalk 0.39
vs 0.26 under fade — it held the mega-chalk as designed) but the
winner-anatomy barbell does NOT beat the smooth fade on our objective.
The fade survives its replacement challenger; F4 closed.

## Addendum 75 (2026-08-05): Review #4 round 2 — generator verdict accepted; two new arms; one misread corrected

Reviewer accepted the LSE falsification and moved the wall to the
GENERATOR ("the co-booms do not exist in the candidate pool"). Triage:

- **N@237 "crisis" (5-trillion claims): MISREAD.** Those columns are
  the GAUSSIAN self-model of our 40 entry scores — the same model
  Addendum 74 showed under-predicts our own realized tails by +7
  weeks. They measure the diagnostic's normality assumption, not the
  sim's covariance. Correction goes in the next reviewer message. The
  legitimate residual question — does the sim ever roll
  slate-breaking collinear game scripts? — is answered by testing the
  remedy directly:
- **HYPER_BOOM (new lever, coded)**: for each top-N games by
  projected total, manufacture a synthetic world (every in-game
  player at his own p98 draw, everyone else p50) and MILP-solve it;
  tag "hyper", injection via pool. This is GAME-level collinear
  inflation — distinct from Q99_WILD (individual players, no
  correlation), so not graveyard-blocked. ARM: HYPER_BOOM=8, chained
  after SHARP on the panel family, on the rebuilt :rev4.
- **"Glass cannon" conditional-peak selection: internally
  inconsistent with their own §1** (selection was just exonerated;
  the weekly max survives every selector) — but zero-code testable:
  SELECT_LSE=0.5 IS conditional-peak ranking (sharp alpha is
  dominated by each candidate's best worlds). ARM: SHARP, running.
  Prediction registered: null-or-worse on tails (it sacrifices
  breadth for depth the pool doesn't contain; PEAK_SLICE's 21 is the
  family prior).

## Addendum 76 (2026-08-05): Assembly batteries — LSE's second falsification triggers; GREEN's generator finds more, concentrates less

Race-free batteries (per-arm roster tables), 2025, 40 entries:

| arm | capture | pool-hit | best-entry overlap (null) | pairs | opt QB pool/best |
|---|---|---|---|---|---|
| CONTROL | 67.5% | 77.8% | 2.00 (2.38) BELOW | 25.8% | 13/18 / 4/18 |
| LSE a=0.08 | 66.9% | 74.3% | 1.78 (2.30) BELOW | 22.7% | 12/18 / 4/18 |
| GREEN2-corrected | 66.9% | 81.2% | 1.56 (2.37) BELOW | 20.2% | 15/18 / 3/18 |

- **LSE: both pre-registered falsifications now triggered** (mean best
  did not rise; overlap 1.78 did not clear the null). The
  depth-rewarding objective actually holds slightly FEWER optimal
  players. F1 is closed with maximal prejudice.
- **Below-null overlap is universal** — three constructions, three
  selectors, all below their random nulls. It is a structural
  property of world-coverage portfolio selection over noisy sims,
  not any single algorithm's defect.
- **GREEN's one real mechanism lead**: pool-hit 81.2% vs 77.8% and
  optimal-QB-in-pool 15/18 vs 13/18 — the per-world-argmax generator
  IDENTIFIES more of the hindsight-optimal slate than the incumbent
  generator mix, at equal capture. If September's skeleton-resampler
  bar ever makes selection sharper, GREEN has more raw material.
  Recorded as the documented lead that keeps GREEN alive as the
  September vehicle (score: exact parity).

## Addendum 77 (2026-08-05): The deletions pass — both never-retested rules are dead weight; M4 concentration refuted

Review #4 F6's deletion tests, each vs the sealed 25 control:

- **NOFADE (OWN_MODEL=off): 26/107**, per-season deltas
  {0,0,0,0,0,+1} — never negative. The chalk fade contributes NOTHING
  post-ensemble. Its pre-registered deletion rule ("if 25 holds,
  delete") FIRES.
- **NOPUNT (PUNT_MIN=0 + PUNT_BOOM=0): 26/107**, mean best 180.6 vs
  179.7 (deltas {0,+2,0,0,-1,0}), program-best max 271.1 (2019). The
  punt mandate + punt-boom valuation contribute nothing and cost a
  little ceiling. Deletion rule FIRES.
- Post-ensemble law vindicated AGAIN: both rules were pre-ensemble
  adoptions with real-looking wins that do not survive the ensemble.
- **M4QBLOCK: 1/107** vs M4LINE 3/107, mean best ~143 vs 152 —
  one-QB-family concentration at 4 entries REFUTED (reviewer F5).
  Week-1 Milly slice: fixed-line first-4, final.
- **DELETE2 launched** (combined OWN_MODEL=off + PUNT_MIN=0 +
  PUNT_BOOM=0): the deletions were tested separately; defaults flip
  ONLY if the combination holds >=25 (interaction guard). If it
  holds: flip code defaults, reseal, update memories — the shipped
  system gets SIMPLER days before week 1, with one fewer live
  dependency (the ownership booster leaves the construction path;
  it remains in QF fade… no — QF's fade IS the deleted rule; the
  booster remains available for field modeling only).

## Addendum 78 (2026-08-05): Review #5 (Sol) triage — two verdicts relabeled, the TD covariance hole confirmed, oracle instrumentation shipped

Sol (OpenAI GPT-5.6, with code access) audited the code paths behind
tonight's conclusions. Four claims VERIFIED against source, with
consequences:

- **Addendum 77 PART-RETRACTED — "the fade is dead" was never
  tested.** OWN_MODEL=off falls back to naive_ownership and the
  leverage penalty still applies (replay.py: `if own is None: own =
  naive_ownership(frame)` -> unconditional proj_tourney fade).
  NOFADE's 26 actually measured TRAINED-vs-NAIVE ownership inside the
  fade — its real finding: the trained ownership booster adds nothing
  to the fade post-ensemble (QF's OWN_MODEL=fade adoption is itself
  now questionable). BARBELL likewise ran barbell+naive-fade, not
  barbell-replacing-fade. DELETE2 (running) is relabeled "naive-fade
  + mandate/boost deletion guard." TRUE_NOFADE (LEV_PENALTY=0) is
  RUNNING on the g2 family; the fade deletion decision waits for it.
- **NOPUNT relabeled**: the p90 punt valuation in build_slates has no
  off switch and stayed active; what 26/180.6 killed is the MANDATE +
  archetype boost only. p90 valuation survives (Sol concurs it
  should).
- **TD independence CONFIRMED — and worse than claimed**: rec_tds,
  rush_tds, pass_tds are independent Poissons on static means in
  simulate.py — uncorrelated with the game factor, the usage draws,
  and EACH OTHER. A QB passing TD and its receiver's TD (the same
  physical event, 6+4 points of joint boom) co-occur only at base
  rates. The single most credible generator-wall mechanism found by
  any reviewer. Build: TD event ledger (draw team passing TDs once,
  multinomial-allocate to receivers, score the QB from the same
  ledger, "other" bucket reconciles means) behind TD_LEDGER=1, with
  Sol's gates: marginals unchanged, held-out joint moments improve,
  THEN panel.
- **Live-path parity risk confirmed**: live_lineups.py hardcodes the
  p90 punt valuation and mirrors the fade — any default flip must
  touch it.
- **Candidate-oracle instrumentation SHIPPED** (engine.py, always-on
  log line): per week — best ACTUAL among ALL candidates vs best
  selected, unselected line-clears missed, actual-best's sim rank.
  Sol's core point stands: every "wall is the generator" claim rested
  on selected-set evidence; the preselection frontier was unobserved.
  Every arm from here on reports it free.
- **SHARP verdict (glass cannon, SELECT_LSE=0.5): 26/107, mean 179.7
  — null as registered.**
- Sol's 88/69 prior (60% field-scale luck / 30% buildable / <=10%
  field blind spots) and its critique of diagnose_portfolio's null
  (Bernoulli, no salary/position/stack constraints; 8-player $47k
  optimum) are recorded as measurement work: the FLEX archive
  subsampling curve is runnable now; classic transport waits for
  September.
- Research posture adopted (Sol F7): operate-and-collect with a
  NARROW budget — corrective tests, candidate-frontier measurement,
  coherent joint-event generation (TD ledger), and
  new-standings-unlocked experiments ONLY. No more tilt/selector/
  dose/anatomy arms.

## Addendum 79 (2026-08-05): Review #5 round 2 — the September research program is now specified

Sol's five new directions triaged into build-ready specs:
reports/september-research-designs.md. Adopted testing order: (0)
instruments — candidate-oracle (shipped) + role-weighted variogram
dependence score (build first in September; energy scores are blind
to miscorrelation); (1) similarity-conditioned Schaake shuffle
(historical within-game rank templates on our calibrated marginals —
imports ALL real joint patterns at once, marginals preserved by
construction; three-arm design vs sim copula and unconditional
templates); (2) cross-entropy rare-world generation (learned
replacement for HYPER's fixed p98 rule; mechanism gate: upper-tail
regret -25% AND candidate-oracle actuals improve, else bury the
family); (3) decision-focused lineup reranker (needs candidate
persistence — REPLAY_CANDIDATES_TABLE pattern; LOW prior, selection
thrice-null); (4) inverse-optimization field model vs skeleton
resampler on ownership/salary/stack/DUP calibration (needs classic
standings); (5) field-relative best-response generation (only after
#4 picks a field model). Vine copulas / Tail-GANs / lineup
transformers deferred indefinitely — 107 slates.

Sequencing decision recorded: Schaake does NOT launch tonight even
if the window allows a build — TDLEDGER (in flight) treats the same
disease (missing joint dependence); two simultaneous dependence
overhauls would confound attribution. TDLEDGER's verdict + oracle
metrics decide whether Schaake is a September-week-1 build or the
program's first 2027 idea.

**Addendum 79b — DELETE2 guard verdict: 27/107, program-best clean
tails.** (Relabeled arm: TRAINED->NAIVE ownership in the fade + punt
mandate/archetype-boost deleted; p90 valuation and the fade itself
retained.) Deltas {0,+2,0,0,-1,+1}, mean best 179.5, max 271.1. No
negative interaction between the partial deletions; the simpler
package holds >= control everywhere it matters. Pending TRUENOFADE
(LEV_PENALTY=0) and DELETE3 (full corrected package) to finalize
which defaults flip. The direction is now unmistakable: post-ensemble,
the system prefers LESS hand-tuning — every deletion tested so far is
null-to-positive.

## Addendum 80 (2026-08-05): TRUENOFADE 23 — the fade earns its keep; the final default package is DELETE2's config

TRUENOFADE (LEV_PENALTY=0, the ACTUAL fade deletion): 23/107, deltas
{0,+1,0,0,-3,0}, mean best 180.5 (up) but tails down. The chalk fade
contributes ~+2 tails post-ensemble — it survives its corrected
deletion test. Sol's audit materially changed an adoption decision:
the mislabeled arm said delete (26); the true arm says keep (23).

The four-arm picture is now coherent:
- fade OFF: 23 (costs tails)
- fade w/ trained own (sealed default): 25
- fade w/ NAIVE own: 26 (booster adds nothing)
- fade w/ naive own + punt mandate/boost deleted: 27 (DELETE2)

**Default flips chosen (pending one confirmatory arm)**: OWN_MODEL
default "" (naive fade — ownership booster leaves construction),
PUNT_MIN default 0, PUNT_BOOM default 0. KEEP: the fade itself, p90
punt valuation, salary floor, stack mandate. Live path
(live_lineups.py) must mirror all three. DELETE3 (in queue) is now
purely confirmatory (predicts ~23-25: it includes the fade
deletion). The reseal happens ONCE, after TDLEDGER's verdict, so a
ledger adoption (if any) ships in the same image.

## Addendum 81 (2026-08-05): HYPER 24 (no adoption; family to CE gate) — and the oracle's first look shows recoverable tails

HYPER (manufactured collinear game worlds, HYPER_BOOM=8): 24/107,
deltas {+2,+2,-1,0,-4,0} — LOSO fails, no adoption — but the highest
mean best of any arm ever (180.9; 2019 arm mean 190.9). The
manufactured-scenario family shows mean-lift with tail-variance;
judgment deferred to the September cross-entropy mechanism gate
(designs doc #2), which supersedes the fixed-rule approach. Note:
_entry_anatomy's generator list is hardcoded and omits "hyper" —
attribution was blind to the new tag (instrument fix for September).

**Candidate-oracle first samples (from the HYPER-2024 run)**: week
sampled — oracle 200.2 was a LEV candidate at sim-rank 155/175,
UNSELECTED; selected-best 190.6; SIX unselected candidates cleared
194 in a week the portfolio missed. Sol's core point materialized on
the first look: the preselection pool contains line-clears the
selector drops. The CANDORACLE control aggregate (in flight, clean
defaults) quantifies the recoverable-tail rate; if it is material,
selection re-opens — this time with the right instrument and against
the right frontier.

## Addendum 82 (2026-08-05): Graveyard mislabel audit — one more unsound burial found; the corrective set is now complete

Erich's question — "with better testing, retry old ideas?" — answered
by AUDIT, not blanket rerun. Every buried post-ensemble arm's env gate
was verified against code:

- **CLEAN burials** (gate exists, verifiably fired, tested what the
  name says): LSE, SHARP, Q99_WILD (post-gsis_id-fix), N_BOOM,
  PEAK_SLICE, VALUE2E, HET, M4 arms, HYPER, SCRIPT_FEEDBACK,
  ALT_CEIL, WR_BOOM, ROOKIE_WIDEN, VACC2. These graves stand.
- **DIV_TILT: burial UNSOUND on two grounds.** (1) DIVTILT2's 16
  total dates it to the PRE-ensemble era — unreliable by the
  post-ensemble law; (2) the lever is column-gated on consensus_div
  and 2019 has NO prop market at all ("prop market unavailable;
  replaying unblended" in the logs) — the arm's best season (2019,
  7/17) occurred where the lever was INERT. Disposition: NOT a panel
  rerun (covered seasons alone can't clear the evidence bar; narrow
  posture forbids new tilt arms) — reclassified to IN-SEASON SHADOW
  CANDIDATE: 2026 has full live prop coverage, so log the divergence
  signal weekly beside persona/env-forecast and grade it on real
  slates before any adoption talk.
- **TRUE_BARBELL launched** (panel family): the last
  mislabeled-untested corrective (Sol's list) — barbell with the fade
  ACTUALLY removed (LEV_PENALTY=0|OWN_BARBELL=1). Prior low
  (fade-removal costs ~2; the barbell must recoup it), but the
  question deserves a real answer, not a mislabeled one.
- **Conditional retests remain tied to adoptions, not nostalgia**:
  if TDLEDGER adopts, VALUE2E (26, nearest miss) gets one re-judgment
  under the new joint structure; if CANDORACLE's aggregate shows a
  material recoverable-tail rate, selection re-opens with
  oracle-aware design — and the selection-era graves revive under
  THAT selector only. No other reruns.

## Addendum 83 (2026-08-05): The candidate-oracle baseline — 8 recoverable weeks sit in the pool; and a draw-order confound caught by co-run control

**CANDORACLE (defaults, instrumented build): the preselection
frontier clears 194 in 30/107 weeks vs the selected book's 22 on the
same build — +8 weeks (+36%) of tails EXIST in the current pool and
selection drops them.** Mean oracle gap 6.9 pts (median 0.5, p90 21);
oracle in the selected 40 only 48% of weeks; the actual-best
candidate's sim-rank is median 53/168 (top-40 only 38%). Precise
correction to "selection is exonerated": all SIM-INFORMED selectors
are equivalent (hence LSE/SHARP/coverage all tie — they read the same
signal, and the sim cannot rank candidates by realized outcome), and
all of them leave ~1/3 of reachable tails unselected. Capturing the
residual needs either (a) MORE ENTRIES — the pool outproduces the
book, which is WHY the entries curve still slopes past 40 (Addendum
74); bankroll-level lever, no code — or (b) a selection signal
ORTHOGONAL to the sim: exactly the decision-focused reranker
(September designs #3), whose priority now RISES with its target
quantified (8 weeks / 6.9 pts). Oracle tag mix: boom 55, lev 24,
dark 12, qbvar 10, game 6 — the leverage batch is a quiet oracle
producer.

**Co-run control catch**: the TD-ledger commit REORDERED the sim's
RNG draw sequence (TD draws moved after interceptions), so the
instrumented build's deterministic streams shifted — CANDORACLE
(defaults, same build) came in at 22 selected-clears vs the sealed
25. Nothing is wrong distributionally; but TDLEDGER and DELETE3 run
on THIS build and MUST be judged against CANDORACLE's 22, not the
sealed 25 (same-build law). Consequence for the reseal: the new
image re-bases the baseline — the final seal includes a fresh
control panel (HARVEST-FINAL-2) to establish the shipping number.

## Addendum 84 (2026-08-05): TDLEDGER negative (18 vs 22) — parametric TD coupling buried; DELETE3 confirms the fade; final package locked

Both judged vs CANDORACLE 22 (same build, same RNG streams — the
draw-order rebase of Addendum 83):

- **TDLEDGER 18/107** ({7,3,1,4,0,3} vs {6,3,3,2,3,5}) — three
  negative seasons, 2024 wiped out (0 clears, max 190.7). The ledger
  passed its gates (marginals preserved, QB-catcher corr created,
  joint boom rate up in isolation) and still LOWERS panel tails.
  Mechanism note for September: by Poisson splitting, the multinomial
  allocation leaves receiver counts marginally Poisson — the actual
  changes were the shared-total QB<->catcher correlation and the
  game-factor coupling of TD means; as implemented, the package
  compresses lineup ceilings. Parametric dependence surgery is now
  0-for-2 (ledger, HYPER); the similarity-conditioned Schaake shuffle
  (real joint patterns, no parametric assumptions) is the September
  vehicle, judged with instrument #0 BEFORE any panel. TD_LEDGER
  stays default-off; code and gate tests remain for re-examination.
- **DELETE3 20/107** — fade removal costs ~2 on this build too
  (TRUENOFADE said the same on the old build). Confirmatory; the
  DELETE2 package (naive-fade + no punt mandate + no punt boost) is
  FINAL for the reseal.

**Addendum 84b — TRUEBARBELL 24 vs co-run 22**: the corrected
barbell-replaces-fade arm (old punt defaults) recoups the fade's ~2
tails ({0,+2,0,0,0,0}) — an ownership-structure term worth ~2 exists
whether expressed as smooth fade or barbell; LOSO fails for adoption
(one positive season) and the fade is simpler + twice-validated, so
the package is unchanged. Corrective set COMPLETE: every mislabeled
arm now has an honest verdict.

## Addendum 85 (2026-08-05): Review #5 round 3 — two retractions, seven fixes; the audit loop catches its biggest fish

Sol audited the day's commits with code access. Verified findings and
consequences, in severity order:

- **TDLEDGER's burial (Addendum 84) is RETRACTED — the arm was
  INVALID, not negative.** replay simulates whole-season frames and
  the ledger factorized team abbreviations alone, pooling every
  KC player-week of a season into ONE TD draw scaled by the first
  game's multiplier. 18-vs-22 measured a broken mechanism. FIXED:
  (game, team) unit grouping + cross-game-independence regression
  test. TDLEDGER2 rerun queued on the fixed build; the parametric-
  coupling question is OPEN again, not buried.
- **The 25->22 "draw-order rebase" (Addendum 83) was self-inflicted
  and is REVERTED**: the off-path now reproduces the pre-ledger RNG
  sequence byte-for-byte. Sealed baselines are comparable again; the
  CANDORACLE oracle numbers (30-vs-22 frontier) remain valid AS
  ORACLE data on their own build, and HARVEST-FINAL-2 (relaunched on
  the fixed image) re-measures both baseline and oracle on the
  shipping config.
- **Ledger reconciliation fixed**: when rostered receiver TD means
  exceed the passer sum, the old code scaled receivers down (broke
  their marginals); the unit total is now max(passer-sum, catcher-
  sum) with other-buckets on both sides — both marginal sets
  preserved, regression-tested.
- **Live/replay blend parity**: the live paths blended DK historical
  PPG while the replay blend that VALIDATED BLEND_W=0.45 uses
  de-vigged prop points. Live is now props-first with DK-PPG
  fallback; div_shadow only logs when the source is real props (it
  was about to spend September grading the wrong market).
- **Live ownership universe**: fade + own_shadow were computed over
  the UNION of upcoming draft groups; restriction now happens before
  ownership normalization.
- **div grader preregistration**: implements sign(div)x(actual-
  market) over |div|>=2 with the frozen first-6-week denominator.
- **Persistence hardening**: candidate rows carry provenance (run_id,
  selected_rank, tail_line, n_entries, n_sims, locks/theses); the
  live path passes the table explicitly (no global env mutation) and
  writes via daemon threads — a stalled BigQuery call can no longer
  block lineup generation.
- **Schaake axis corrected** in the design doc (ranks ACROSS matched
  games per role — the within-game axis would not preserve marginals).
- Sol's "defaults not applied" finding was timing (reviewed pre-flip
  HEAD): the DELETE2 package is committed and deployed.

Process law reinforced: the GREEN2 env typo, the NOFADE mislabel, and
now the TDLEDGER grouping defect were all caught by AUDIT, not by the
panel — the panel produces a number either way. Instrument-level
review before verdict-level interpretation.

## Addendum 86 (2026-08-05): Emerging-technologies program LAUNCHED — five parallel workstream builds

Erich's directive: build everything whose data exists today; adopt
only as proven. The program doc (reports/emerging-technologies-plan.md)
is the specification; its §3 prerequisites were completed by tonight's
round-3 fixes. Five builds now running in parallel isolated worktrees:

1. **Shared infrastructure** (§4/16.1): run-context, normalized
   candidate schemas, machine-readable config manifest, role-weighted
   variogram dependence suite (instrument #0 made real).
2. **GFlowNet generator v0** (workstream A): legal-construction
   environment with masks, trajectory-balance training, toy-
   distribution validation, equal-count gate vs MILP baseline.
3. **SBI calibration v0** (workstream B): 3-parameter registry
   (game-factor sigma, usage concentration, TD allocation), summary
   builder, synthetic truth-recovery gate — with an RNG-parity test
   so parameter injection cannot repeat the draw-order accident.
4. **Online conformal + foundation challengers** (workstreams E/F):
   append-only adaptive calibration state, risk-control knob,
   walk-forward usage-sequence benchmark (Chronos if installable;
   TabFM availability probe).
5. **Evidence-to-prior pipeline** (workstream D): schema + supersede/
   conflict logic (conflicts widen variance), extractor contract with
   injection defenses, effect-model stub — fixtures now, live news
   wiring is the one data-gate besides tracking.

**Data-gated (the only deferrals, per directive)**: workstream C
tracking embeddings (needs Kaggle BDB 2026 download under Erich's
account) and evidence LIVE feeds (September news flow). Everything
else is being built tonight. Adoption bar unchanged: every workstream
carries the plan's own mechanism gates + the panel/LOSO laws — built
is not adopted.

Meanwhile the close-out continues: HARVEST-FINAL-2 + TDLEDGER2
running on the fixed image (rev family).

## Addendum 87 (2026-08-05): HARVEST-FINAL-2 = 27/107 — the shipping baseline, byte-identical to its validating arm

The rebased shipping baseline (adopted defaults: naive fade, no punt
mandate/boost; fixed draw order; all shadow collectors aboard):
**27/107, mean best 179.5, median percentile 14.2%** — per-season
{2019:5, 2021:3, 2022:3, 2023:4, 2024:6, 2025:6}, BYTE-IDENTICAL to
the DELETE2 arm that validated the package. Cross-build exact
replication = the determinism program and the round-3 RNG-parity fix
verified in one shot. This replaces HARVEST-FINAL (25) as the number
every future arm must beat. TDLEDGER2 (fixed grouping) launched
against it. Ops note: the box crashed twice under parallel local
load — the emerging-tech workstreams now proceed ONE at a time,
targeted tests only, per the standing all-heavy-compute-on-Cloud-Run
rule.

## Addendum 88 (2026-08-05): Emerging-tech program — build results and first verdicts

All six workstreams BUILT, merged, targeted-tested. First real
verdicts, each by the plan's own gates:

- **GFlowNet: GATED OUT of GPU spend.** Mechanism clean (100% legal
  by construction, zero MILP-mode overlap, QB entropy 2.79 vs 0) but
  the §5.8 cheap-diversity baselines both beat it at equal candidate
  count on synthetic: world-argmax frontier 115.6 (+7.9 union gain)
  and Gumbel-MILP 114.1 (+6.8) vs GFlowNet 109.9 (+5.4) — in 0.4s vs
  6.6s training. Its own falsification rule applies. The v0
  environment/TB code is archived for a future field-relative-reward
  revisit; meanwhile the winner of its own gate IS our production
  boom generator, re-validated a third way. Gumbel-MILP (+6.8 cheap)
  is a NEW candidate-batch idea worth a real-slate arm in September.
- **Chronos (time-series FM): baselines-win.** Loses to EWM/Kalman
  on all synthetic buckets, worst at cold start (pinball90 2.10 vs
  1.28) — §10.3 rule keeps it out; harness ready for real sequences.
- **SBI: 2 of 3 parameters identifiable** (game-factor sigma, usage
  concentration; TD allocation fixed at default per §6.7); golden-
  hash RNG-parity tests now pin default draws byte-exactly.
- **Tracking: v0 SHIPPED with real crosswalk** — 18 weeks in 9s,
  1,384 players, 96.3% high-confidence nfl_id->gsis matches after a
  dob-format fix (0% -> 96.3%; 51 honest review rows). Traits sanity:
  Tyreek Hill fastest (p90 speed 8.40). Next gate: shadow-feature
  eval on thin-history players. Free in-season refresh path noted:
  nflverse NGS weekly aggregates (same family as adopted qb_cpoe).
- **Evidence + conformal: built, fixture-proven, data-gated** (live
  news / 2026 scored rows). Zero code needed at activation beyond
  wiring documented in the workstream reports.
- **Config manifest caught real drift on first run** (app legacy
  path PUNT_BOOM=2 vs adopted 0 — fixed; zero-discrepancy test now
  permanent).

## Addendum 89 (2026-08-05): TDLEDGER2 19 vs 27 — the valid burial; parametric TD coupling is dead

TDLEDGER2 (fixed (game,team) grouping, RNG-parity default,
reconciled marginals — every round-3 defect corrected): **19/107 vs
the HF2 co-run control's 27** ({5,3,4,3,1,3} vs {5,3,3,4,6,6};
mean best 178.4 vs 179.5; 2024 -5, 2025 -3). This time the arm is
VALID — and the verdict is unambiguous: hand-specified TD event
coupling reduces tails even when mean-preserving and correctly
grouped. Family buried on clean evidence. Consequences: TD_LEDGER
stays default-off permanently (code + gates remain as the SBI
td_alloc_k host); the reconciliation-identities direction is
DEPRIORITIZED behind Schaake (which imports real joint patterns
without specifying mechanisms) — Schaake is confirmed as September
dependence build #1, gated on instrument #0. The N_GUMBEL candidate
batch (this hour's gate winner, +6.8 synthetic union gain) is the
one new-generation lever left with a live shot; arm queued.

## Addendum 90 (2026-08-05, FINAL): GUMBEL 26 vs 27 — null; the program closes on the sealed baseline

GUMBEL (N_GUMBEL=20, perturb-and-MAP diverse candidates — the winner
of the GFlowNet's own cheap-diversity gate): **26/107 vs HF2's 27**,
per-season {5,3,3,4,6,5} vs {5,3,3,4,6,6}; mean best 179.5 vs 179.5
(identical); median percentile 14.2 vs 14.2. One season -1, five
seasons dead level. The synthetic gate's +6.8 union-frontier gain did
NOT transport to real slates — the third time a diversity mechanism
has looked good in isolation and nulled on the panel (Q99_WILD,
GFlowNet, now Gumbel). N_GUMBEL stays default-off; the code and its
test remain as the archived generator-diversity family.

**PROGRAM CLOSE.** Shipping baseline stands at HARVEST-FINAL-2 =
27/107 (mean best 179.5, median 14.2%, max 271.1). Per-week bests
archived at ~/nfl-panels/gumbel_weekly.csv. Final tally of the
post-seal wave: 30+ arms tested, ONE adoption (the deletion package:
naive fade + no punt mandate + no punt boost, 25 -> 27 with a simpler
system), three invalid arms caught by audit rather than by the panel,
six research workstreams built and gated, and every remaining idea
either buried with cause or scheduled with a pre-registered gate.

## Addendum 91 (2026-08-05): ACTION 4 — the salary floor is NOT load-bearing (26 vs 27, mechanism confirmed live)

Sol's clean deletion (MIN_LINEUP_SALARY=0, not a 47.5k dose): **26/107**
per-season {5,3,3,4,6,5} vs HF2 {5,3,3,4,6,6}; mean best 179.9 vs
179.5 (UP); max unchanged 271.1. The deletion FIRED verifiably — the
salary-left distribution moved from the floor-clamped "median $200 /
share>$1k ~0%" to median $100-300 with 5-16% of entries leaving over
$1k — so the solver did explore sub-$49k builds and simply did not
prefer them enough to change tails.
Verdict: within noise, one season -1, mean-best slightly better. The
floor is NOT the load-bearing rule its pre-ensemble validation (2026-
07-26, 180.1 -> 182.3) implied — but deleting it also buys nothing, so
the rule STAYS on the "no reason to change" principle rather than on
its old evidence. Gemini's B4 instinct (pre-ensemble verdict, retest
it) was right to raise; Sol's version of the test (clean deletion, not
a dose) is what made the answer interpretable.
CAVEAT recorded: the control here is HF2's 27 from an earlier image.
The persistence work since is behavior-neutral by construction
(logging + provenance only), and the relaunched ACTION 1 control will
confirm that by reproducing 27 on the current image; if it does not,
this verdict is re-judged against whatever ACTION 1 measures.

## Addendum 92 (2026-08-06): The canonical panel — frontier confirmed, crowd-out REFUTED, objective flat

Panel 20260805-hf5 (promoted, acceptance-gated: 17,851 candidates /
107 slates / 31,107 player-feature rows / 107 checksum-verified score
artifacts; every slate's selection reproduced from persisted masks).

**Frontier (§6.1 gate PASSES)**: pool clears 194 in 35/107 vs the
selected book's 27 — **8 recoverable weeks across 4 seasons** (2019
wk1/4/15, 2022 wk5/12, 2024 wk14, 2025 wk10/17). At 187 the gap is
12; at 200 it is 6. Mean regret to the pool oracle 6.8 pts.

**The reranker's premise narrowed sharply.** corr(oracle sim-rank,
regret) = +0.362 unconditionally but **+0.030** among the 54 weeks
where the oracle went unselected (the old build's inflated figure was
+0.428/+0.211). "The simulator systematically buries winners" is NOT
the mechanism on the shipping system — recoverable oracles sit at
ranks 48-138 with no usable gradient. Any reranker must supply
information ORTHOGONAL to the simulator or it will find nothing.

**ACTION 2 (leave-one-generator-out, both bounds, frozen pool) —
the crowd-out hypothesis is REFUTED**:
| generator | cand share | selected share | d_clears if removed |
|---|---|---|---|
| boom | 24% | 65% | **-15** (27 -> 12) |
| dark | 6% | 11% | -3 |
| qbvar | 19% | 9% | -1 |
| lev | 48% | 8% | -1 |
| game | 7% | 8% | 0 |
Removing `lev` — 48% of the pool, only 8% of selections, source of 4
of the 8 recoverable oracles — costs ONE clear. The selector is not
crowding out a valuable batch; boom's selection dominance is EARNED
(removing it costs 15 clears). Gemini's stratified-quota proposal
would have been actively harmful; Sol's insistence on measuring
deletion before dosing was correct. Bonus finding: `dark` is the
highest value-per-candidate batch (6% of pool, 3 clears).

**ACTION 3 (tail-line sensitivity, every portfolio scored at ALL
lines)**: selecting at 187 / 194 / 200 yields c194 of 26 / 27 / 27,
mean best 180.3 / 179.4 / 179.5, regret 6.0 / 6.8 / 6.7. The
objective threshold is FLAT within noise — 194 keeps the most
194-clears and 187 the best mean/regret. No change; the economic
question stays open until real payout curves exist (plan §B3).

## Addendum 93 (2026-08-06): Workstream A — the reranker is FALSIFIED; the frontier is not recoverable by ranking

One nested LOSO comparison on the canonical panel, preregistered
before any result was viewed (target = actual minus simulated
location; ridge; slate as the unit; bounded shift applied to world
totals then the UNCHANGED coverage selector rerun, never a top-40
sort):

| arm | clears | mean best | regret | seasons better |
|---|---|---|---|---|
| A0 incumbent | 27 | 179.4 | 6.8 | — |
| A1 structure/provenance | 28 | 179.9 | 6.3 | 2 |
| A2 + market/model disagreement | 27 | 179.6 | 6.6 | 1 |
| A3 + ownership/uncertainty | 24 | 178.4 | 7.9 | 0 |
| A4 shuffled control | 25 | 179.4 | 6.9 | 0 |

**No arm meets §7.8's adoption bar** (>=4 seasons improved, no
catastrophic season, beats the control). A1's +1 clear is
concentrated in 2 seasons — inside the +/-2-3 noise band and barely
separated from the shuffled control. Decisively: **adding the
orthogonal features made it WORSE** (A2 flat, A3 -3). The hypothesis
that pre-lock market/model disagreement or ownership can identify the
buried winners is refuted on the only data that could test it.

This closes the loop opened by the +0.428 correlation: that statistic
was inflated (+0.030 among unselected oracles on the shipping build),
and with the honest number there was never a gradient to learn. The
8 recoverable weeks are real but are NOT recoverable by re-ranking a
frozen pool — no pre-lock signal in our possession separates the
oracle from its 160 neighbours. Capture, if it comes, must come from
MORE ENTRIES (the pool outproduces the book) or from genuinely new
information (plan Workstream E), not from smarter selection.

Selection is now falsified five independent ways: LSE, sharp-LSE,
QB-concentration, dollars-objective, and this decision-focused
residual reranker. The family is closed.

## Addendum 94 (2026-08-06, FINAL): Preseason sealed

**Shipping system: HARVEST-FINAL-2 config, 27/107 weeks best-of-40
>= 194, mean best 179.4, median percentile 14.2%** — re-verified on
the canonical panel (20260805-hf5) with every slate's selection
reproduced from persisted masks. App + 14/14 jobs deployed on the
final image (nfl-dfs-app rev 00050); full suite green (515 tests).

Post-review-6 program, complete:
- ACTION 0 persistence contract — closed after three audit rounds
  (provenance before dedupe, NULL labels, two-level run identity,
  full masks + 187/194/200 grid, score artifacts, per-player feature
  snapshot, all-slate acceptance, idempotent promotion).
- ACTION 1 canonical harvest — promoted; 17,851 labeled candidates,
  31,107 point-in-time player rows, 107 verified artifacts.
- ACTION 2 LOGO — generator crowd-out REFUTED.
- ACTION 3 tail-line — objective flat 187/194/200.
- ACTION 4 salary floor — not load-bearing; rule kept (no gain).
- Workstream A reranker — FALSIFIED; selection closed five ways.

Nothing adopted this round; the shipping config is unchanged. What
the round produced is a measurement apparatus that cannot lie the way
the previous one did, three retracted claims corrected, and four
families closed with evidence instead of intuition. September's live
levers are candidate GENERATION (Schaake, cross-entropy), new
information (market movement, evidence, tracking), and entry volume.

## Addendum 95 (2026-08-06): Scope correction to Addenda 93-94

Sol's review of the close-out flags two overclaims in my wording.
Both accepted:

1. **"No scoring gain was available" is unknowable** and should never
   have been written. The defensible statement is: no change TESTED
   this round earned adoption, and the tested space was bounded by the
   current simulator and a static, historically-reconstructable
   feature set.
2. **"Selection is closed" is too broad.** The correct claim is:
   **selection is closed WITH THE CURRENT SIMULATOR AND STATIC FEATURE
   SET.** Five falsifications (LSE, sharp-LSE, QB-concentration,
   dollars, residual reranker) all read either the same simulated
   worlds or features reconstructable from the existing pipeline. They
   do not rule out a selector fed by information the system does not
   yet have.

**Reopening condition (preregistered here so it cannot be
rationalized later):** a reranker/selector may be revisited ONLY when
a genuinely new pre-lock signal exists — market MOVEMENT and
cross-book dispersion, activated evidence features, tracking traits
with point-in-time coverage, or a materially different simulator
(e.g. an adopted Schaake dependence model) — AND its evaluation is
frozen BEFORE the new outcomes are observed. Retrospective tuning on
these same 107 slates is panel mining and is forbidden.

Sol's priority order for September, adopted verbatim: (1)
similarity-conditioned Schaake, gated on held-out variogram +
marginal preservation; (2) fixed-budget epistemic-scenario generation
(ensemble members, market movement, coherent role alternatives); (3)
cross-entropy rare-world generation, requiring ACTUAL candidate-oracle
improvement before any panel; (4) prospective 2026 collection of
market-movement / evidence / tracking features; (5) entry-volume
analysis using REAL contest costs and payout curves (blocked today —
payout.py is stylized and classic-format rank/score curves do not
exist yet; this is an economics question, not a modelling one).

## Addendum 96 (2026-08-06): Workstream E first results — market movement and cross-book dispersion are both NULL

Prop-market history is richer than assumed: 2023-2025, ~130 snapshots
per season (7-10 per week), 2 books — enough to compute movement and
dispersion strictly point-in-time (snapshots before commence_time
only, never a closing line).

- **Movement (open -> last pre-lock)**: correlation with OUR
  projection residual is ~0 across every market (|r| <= 0.018 on
  1.2k-7.3k player-weeks). The market moves, but not toward anything
  our projection is missing.
- **Cross-book dispersion**: an initial +0.12 on rush yards was MY
  ARTIFACT — a pivot with fillna(0) conflated "no dispersion data"
  with "zero dispersion". The clean per-player-week join gives
  **+0.038 overall and +0.034 / +0.081 / +0.029 by season** — small
  and unstable. Fails the plan's §11.5 step-2 gate (held-out residual
  improvement) and the stability rule.

Neither justifies a feature, a scenario family, or wider
distributions. Recorded so September does not re-mine the same
signal: only 2 books are covered, so a genuine dispersion test needs
a wider book panel (paid Odds API tier), not more work on this data.

**Addendum 96b — tracking traits v0: NO residual gain.** BDB 2023
traits (recv speed p90, accel p90, separation mean, route depth)
crosswalked to 1,333 players and tested on 2024 outcomes (strictly
later season) against a salary+position baseline: MAE 5.007 -> 5.006
overall (+0.02%, nothing) and 4.023 -> 4.034 on THIN-history players
(<17 prior games) — slightly WORSE on the exact population they were
built for. Fails plan §11.5 step 2; traits do not enter construction.
Honest caveats for September: these are v0 aggregates, not the §7.4-7.5
learned encoder; coverage is one season of pass plays; and the
baseline here is salary+position, not the full component model. The
crosswalk (96.3% high-confidence) and trait pipeline stand ready if
the encoder phase is ever attempted, but on current evidence tracking
is NOT a scoring lever.

## Addendum 97 (2026-08-06): Generation-arm audit — first cloud runs invalidated; mechanisms repaired

The first Schaake, EPI and CE executions must not be used for a verdict.
A code audit found mechanism-level differences from the preregistered
design, and each was corrected before any adoption decision:

- **Schaake:** historical percentiles were used as direct indices into
  current sorted draws. Repeated templates therefore repeated quantiles and
  changed player marginals. The shuffle now converts the sampled template
  sequence to an exact rank permutation, with an invariant test requiring
  every player's complete draw multiset to remain unchanged. The replay
  diagnostic now reports realized held-out variogram and joint-upper-tail
  Brier scores, plus exact marginal preservation, rather than merely the
  distance between two simulated correlation matrices. Similarity matching
  now uses the replay's actual pre-lock game total, spread, pace, neutral
  pass rate and usage-concentration fields.
- **EPI:** uncovered seasons previously ran 24 boom solves and zero EPI
  solves, making the purported fixed-budget arm 16 slots smaller. EPI now
  carries complete ensemble-member point vectors into the slate, uses
  complete market/model and high-disagreement-game belief vectors, and
  restores missing or duplicate slots with incumbent boom worlds. DST rows
  without epistemic inputs retain their baseline projection rather than
  receiving a false zero-point belief. EPI/CE automatically replace boom
  slots when N_BOOM is not explicitly supplied.
- **CE:** the initial score split favored one arbitrary slate team against
  every other team, the proposal was scored with an illegal value-greedy
  nine-player proxy, and earliest-round elites were used. CE parameters are
  now game-local, pass/usage changes redistribute within teams, each sampled
  environment is scored by the real legal stacked MILP, only final-round
  elites generate candidates, truncated-normal importance weights match the
  bounded sampler, and low ESS actively prevents further proposal collapse.
  Failed/duplicate CE slots fall back to boom worlds.

The repaired code is test-green, but that is a mechanism result—not a score
result. All three arms require fresh same-image runs. The executions started
before this addendum are explicitly invalidated and cannot be cited as null,
positive or negative evidence.

## Addendum 98 (2026-08-06): EPI fixed-budget arm — 23/107, NEGATIVE

First valid run of the repaired epistemic-scenario generator
(N_EPISTEMIC=16, budget maintained by automatic boom replacement,
complete ensemble/market/model belief vectors, DST rows keeping
baseline projections):

**23/107 vs the 27 baseline** — per-season {3,3,2,3,6,6} vs
{5,3,3,4,6,6}; mean best 178.4 vs 179.4; three seasons worse, three
level, none better. Belief-scenario candidates do not earn their
slots: replacing 16 boom solves per slate with market-heavy,
model-heavy, ensemble-member and high-disagreement-game beliefs COSTS
four line-clears.

Mechanism note for the graveyard: the arm is a fair test this time —
budget held constant (the invalid first run silently ran 16 slots
short on market-uncovered seasons), scenarios are complete vectors
rather than per-player tilts, and failed/duplicate slots fall back to
boom. The result is that the incumbent boom generator's worlds are
better raw material than alternative BELIEFS about the means. This is
consistent with the leave-one-generator-out finding (removing boom
costs 15 clears) and with the reranker falsification (pre-lock belief
disagreement carried no usable signal). Workstream B closes.

**Schaake: still unmeasured.** Its 2025 diagnostic ran on a biased
subset — replay hands the diagnostic a WHOLE-SEASON frame and the
role assignment ranked salary across all 18 weeks at once, labelling
~3 players per team for the season (n_pairs=11, one week-1 line).
Roles, pair correlations and the point-in-time template cutoff are
now keyed per (season, week); the run must be repeated. The
marginal-preservation invariant it reported (exact) stands, since it
does not depend on the grouping.

## Addendum 99 (2026-08-06): Schaake repaired 2025 Cloud Run gate — NEGATIVE

The repaired dependence-only gate ran on Cloud Run execution
`schaake-gate-2025-ba157ab-24b2g`, pinned to image
`sha256:1096e1b92319f53446bc36f5777b0ca0caf250ad5c7b505c2c5ebd7c6924b8cb`.
Its prior image smoke test passed the whole-season role grouping,
distinct per-game random stream, and exact-marginal checks.

The full 2025 diagnostic then produced all 18 machine-readable weekly
records and all required skill pairs (1,686 pair observations):

| Measure (lower is better) | Production | Schaake |
| --- | ---: | ---: |
| Variogram error | 0.158437 | 0.161294 |
| Joint-q90 tail Brier | 0.020284 | 0.020443 |

Every player's draw multiset was exactly preserved and no required pair was
missing, so this is a valid comparison rather than another diagnostic
failure. Schaake is worse on both preregistered held-out measures. It does
not proceed to a candidate-oracle or scoring-panel arm, and it is not
enabled in production.

The execution was deliberately cancelled after the gate record had been
emitted, while the unrelated baseline replay/selection tail was still
running. The cancellation neither changes nor invalidates the already
complete dependence result. The formerly broken `replay-g2-2025` Cloud Run
job was also repinned to this immutable image with strict diagnostic failure
handling, so a future replay cannot silently swallow a Schaake exception.

## Addendum 100 (2026-08-06): Cross-entropy worlds — ADOPTED at fixed budget

The repaired cross-entropy (CE) generator was evaluated in two Cloud Run
stages on the same frozen image (`ba157ab`, digest
`sha256:1096e1b92319f53446bc36f5777b0ca0caf250ad5c7b505c2c5ebd7c6924b8cb`),
over all 107 slates from 2019 and 2021--2025. CE samples bounded,
game-local pace/pass-tilt/scoring-split/usage-concentration worlds, scores
them with the real legal stacked MILP, and uses final-round elite worlds.
Failed or duplicate CE candidates fall back to incumbent boom worlds.

**Stage 1 — union frontier gate (`N_CE=12,N_BOOM=40`).** Adding 12 CE
candidates to the incumbent 40 boom solves increased the *actual* candidate
oracle from **29 to 38 clears at 194** and mean oracle score from **184.58
to 187.83**. The improvement appeared in every season:

| Season | Baseline oracle mean / clears | CE-union oracle mean / clears |
| --- | ---: | ---: |
| 2019 | 191.81 / 6 | 196.69 / 8 |
| 2021 | 181.42 / 3 | 183.73 / 3 |
| 2022 | 182.48 / 4 | 184.64 / 5 |
| 2023 | 181.28 / 3 | 184.89 / 6 |
| 2024 | 182.84 / 6 | 184.70 / 7 |
| 2025 | 188.06 / 7 | 192.79 / 9 |

This earned the equal-budget scoring arm; the union result is not used as a
production score claim.

**Stage 2 — fixed-budget adoption test (`N_CE=12,N_BOOM=28`).** Replacing
12 of 40 boom solves rather than enlarging the pool produced **29/107
selected clears at 194**, versus the 27 baseline, and mean best **181.3**
versus **179.4**. Per season the result is `{4,3,3,5,7,7}` against baseline
`{5,3,3,4,6,6}`. The effect is modest (+2 clears; 2019 loses one clear),
but it passes both the preregistered actual-frontier and equal-budget scoring
gates. CE is therefore adopted, not overclaimed as a large effect.

Production is set to `N_CE=12,N_BOOM=28` on the live app and `project-slate`.
The deployed image is digest
`sha256:28de80b3a615fdf8a3fbbce5f1bb7c07bcc101acbcdab65d40cf9cca1781d57f`;
it additionally fixes the harmless-but-noisy empty two-way-prop fallback in
older seasons. Schaake and EPI remain off/closed; standard boom generation
retains 28 slots and remains the fallback if CE cannot produce a unique
candidate.

## Addendum 101 (2026-08-08): Corrected-universe baseline established; exact replay gate fails

**This addendum supersedes Addendum 100's production conclusion.** The
subsequent independent replay-universe audit found that the 27/107 book
contained 256 selected lineups that fail authoritative historical repricing.
The later 17/107 rebaseline was also invalid because historical DST aliases
dropped 478 salary rows. Additional repairs restrict the target season to the
actual Sunday main slate, validate skill and DST salaries against the
canonical opponent before aggregation, and use the canonical DK DST scorer.
CE's independent confirmation then scored 26/107 against a 27 control, so CE
returned to research-only; production research defaults are again
`N_CE=0,N_EPISTEMIC=0,N_GUMBEL=0,N_BOOM=40`.

The first complete corrected baseline is
`20260808-livefaithful-b3-ee6f433` on immutable digest
`sha256:6e34cb1f3580be71ad2acd50f0faeacf45b59a7039fe7e32b0996ecf26dda9d0`:
107/107 slates, 17,426 candidates, exactly 40 selected per slate, **18/107
selected clears at 194**, mean selected best 175.31, and 24/107 pool-oracle
clears. Replay/live mean parity and the canonical acceptance gate passed; the
panel was promoted by execution `accept-replay-panel-mmdgr`.

The mandatory same-image reproduction
`20260808-livefaithful-b3r-ee6f433` also scored 18/107, but the exact gate
failed in execution `compare-exact-replay-pckdb`. All 50,098 persisted player
features match within the registered tolerance and all actual candidate
scores match. Nevertheless, 2019 and 2024 have 14 roster keys absent from
each opposing arm, 41 differing selected flags, and 22 non-identical
candidate-world artifacts; 2021, 2022, 2023, and 2025 are exact. Aggregate
headline equality therefore does not establish reproducibility.

The already-complete `MODEL_ENSEMBLE=1` ablation
`20260808-a02-ensemble1-ee6f433` (18/107, mean 174.55) receives **no verdict**
until the default same-image control passes exact replay. The next valid work
is determinism instrumentation/hardening at the component-to-simulator
boundary, followed by a fresh baseline plus exact same-image reproduction.
No production promotion and no new scoring arm may bypass that gate.

## Addendum 102 (2026-08-08): One-slate probe isolates unstable tied-world ranks

The first repaired-image 2019 probe pair ran on immutable digest
`sha256:efa18a9a56b62c5c2606eaae3ad37a9765306863a389de8d4af09f8329545a55`
as executions `replay-det19a-2019-lzfjv` and
`replay-det19b-2019-45g2g`. Each persisted the same 164 candidate keys for
2019 Week 1 and exactly 40 selected entries. More importantly, both workers
logged the same raw component hash (`77d4194f...`), canonical component hash
(`3a5abdc4...`), and `5e-11` maximum boundary adjustment.

Exact comparator `compare-exact-replay-g5hf5` still failed, but sharply
narrowed the defect. All 335 player snapshot keys and values matched, all 164
candidate roster keys matched, all actual scores matched, and selected flags
were identical. Per-player simulated summaries were also exact. Only the
joint world assignment differed: the 164x10,000 candidate-total artifacts had
a maximum 3.1025-point delta, which changed three threshold masks and several
candidate quantiles.

The marginal shapers used NumPy's default unstable quicksort twice to turn
each player's outcomes into ordinal ranks. Simulator output contains many
equal outcomes; CPU-dispatched sort implementations may permute those ties
differently. That preserves every player's marginal distribution while
changing which players boom together in a world—the exact observed failure
shape. Commit `1ab4d32` replaces both TabPFN and empirical marginal ranks with
a stable sort whose explicit tie-breaker is the original simulation-column
index. No score claim follows. The 2019 pair must be rerun on the new image;
2024 and all full panels remain blocked until it passes exactly.

The fresh post-fix pair (`replay-det19c-2019-87z8s` and
`replay-det19d-2019-cjgvc`) passed exact comparator execution
`compare-exact-replay-zznbf`. All 335 player snapshots, all 164 candidate
records, every selected flag and threshold mask, candidate ordering, and the
entire 164x10,000 totals matrix matched with zero delta. Component hashes also
remained identical to the pre-fix pair, confirming that stable tie assignment
alone repaired the observed 2019 world drift. The separate 2024 proof remains
mandatory before a full baseline can launch.

## Addendum 103 (2026-08-08): Both formerly drifting seasons pass exact smoke

The independent 2024 pair on the same immutable digest ran as
`replay-det24a-2024-bkhfb` and `replay-det24b-2024-8zvzx`. Both recorded raw
component hash `96e62bc6...`, canonical hash `b1e23c15...`, and the same
`5e-11` maximum adjustment. Comparator execution
`compare-exact-replay-mrdnx` passed: all 700 player snapshots and 161
candidate records matched, candidate ordering did not move, every candidate
metric/mask/selected flag had zero mismatches, and the complete 161x10,000
totals matrix was bit-for-bit identical.

Together with the 2019 pass in Addendum 102, the cheap cross-worker gate is
closed on both seasons that failed the original six-season replica. This is a
measurement-integrity result, not a scoring improvement. The next allowed
step is a new 107-slate default baseline followed by a full same-image exact
replica; no arm verdict or production change may precede those gates.

## Addendum 104 (2026-08-08): Deterministic 107-slate control accepted and promoted

Fresh panel `20260808-deterministic-baseline-c616390` ran all 107 corrected
Sunday-main slates on immutable digest
`sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`
with the frozen default (`MODEL_ENSEMBLE=3`, possession mode,
`N_CE=0,N_EPISTEMIC=0,N_GUMBEL=0,N_BOOM=40`). Its six season execution IDs
are retained in the panel report. Check execution
`accept-replay-panel-2t7vn` and promotion execution
`accept-replay-panel-mlbxt` both passed.

The accepted control contains 17,432 candidates, exactly 40 selected per
slate, and 50,098 unique player snapshots. Replay/live mean parity passed
with zero blend error, zero missing candidate slates/roster players and a
maximum candidate-mean reconstruction error of 0.0000236. Results are
**26/107 at 187, 11/107 at 194, and 1/107 at 200**, with mean selected best
173.06; pool-oracle clears at 194 are 20/107. At 194 the season split is
`{2019:4, 2021:1, 2022:0, 2023:0, 2024:3, 2025:3}`.

This does not mean the determinism repair worsened football prediction by a
clean seven clears: the image bundles stable tied-world assignment, component
canonicalization, and removal of duplicated old training rows. It does mean
the prior 18/107 checkpoint cannot remain the arm control because its joint
worlds were not reproducible. The promoted 11/107 panel is the only current
control, pending its mandatory full same-image exact replica. No scoring arm
may be interpreted before that replica passes.

## Addendum 105 (2026-08-08): Full 107-slate same-image replica passes exact gate

Replica panel `20260808-deterministic-replica-c616390` ran from the same
immutable digest and frozen configuration as the promoted deterministic
control. Its six season executions were `replay-detrep1-2019-jk6g9`,
`replay-detrep1-2021-2hm8h`, `replay-detrep1-2022-l7kgq`,
`replay-detrep1-2023-r6mqz`, `replay-detrep1-2024-9jdm8`, and
`replay-detrep1-2025-qmpp2`. Check-only acceptance execution
`accept-replay-panel-2qfbr` passed with the same 17,432 candidates, 107
slates, 50,098 feature rows, and 11/107 selected clears at 194 as the
promoted control.

Exact comparator execution `compare-exact-replay-4j5hz` then passed against
the promoted baseline. All 50,098 feature keys and all 17,432 candidate keys
joined with no keys unique to either side and zero registered mismatch
counts. Candidate simulation summaries had zero numeric delta, candidate
ordering never moved, and every one of the 107 roster-aligned 10,000-world
score matrices was bit-for-bit identical. Warehouse feature-value round-trip
noise remained within the registered tolerance (maximum `3.56e-15`).

The full measurement/reproducibility gate is therefore closed. This is not a
scoring improvement, and the accepted control remains 11/107. The next valid
experiment is frozen A01 (`BLEND_MODEL_WEIGHT=1.0`), followed only after its
mechanism-aware verdict by a fresh A02 (`MODEL_ENSEMBLE=1`) on this same
image. Results from the obsolete `ee6f433` arms remain non-transferable.

## Addendum 106 (2026-08-08): A01 model-only blend deletion is valid but unsupported-neutral

Fresh A01 panel `20260808-a01-modelonly-c616390` changed only
`BLEND_MODEL_WEIGHT=1.0` on the deterministic control image and fixed
`0/0/0/40` generation budget. All six season executions completed. Generic
baseline acceptance execution `accept-replay-panel-xmdlw` reported 17,422
candidates, all 107 slates, 50,098 unique feature rows, zero missing joins,
and candidate/player mean parity. It exited non-zero only because its
baseline-specific assertion requires persisted covered means to equal the
adopted 45/55 blend; an intentional model-only deletion cannot satisfy that
assertion. This expected failure is not treated as arm invalidation.

The purpose-built `blend` audit in execution
`compare-adoption-panel-bc4qd` passed with no failures. Market inputs and
post-shaping model means were invariant, the treatment mean equalled the
model-only mean, 15,538 covered player-weeks moved by 0.941 points on average,
uncovered means did not move, all 53 no-market slates reproduced exactly, and
candidate/player mean error stayed below `2.36e-05`.

Scoring did not support removal. Model-only tied the control at **11/107**
clears at 194, but fell **26→22** at 187, rose **1→3** at 200, lowered mean
selected best **173.06→172.14**, and lowered pool oracle **20→19**. Its
season-194 deltas were `{2019:0, 2021:0, 2022:0, 2023:+2, 2024:-1,
2025:-1}`. Neither the deletion-improves gate nor the reverse strong-support
gate passed, yielding the preregistered `unsupported-neutral` disposition.
Model-only is not adopted; the incumbent blend remains the operational
default without overclaiming strong positive evidence. A02 K=1 is next.

## Addendum 107 (2026-08-08): A02 K=1 improves aggregate score but fails stability gate

Fresh A02 panel `20260808-a02-ensemble1-c616390` changed only
`MODEL_ENSEMBLE=1` on the deterministic control image and fixed `0/0/0/40`
generation budget. All six season executions completed, and check execution
`accept-replay-panel-w86nj` passed: 17,423 candidates, 107/107 slates, 50,098
unique feature rows, zero missing joins, and replay/live mean parity.

The first mechanism audit (`compare-adoption-panel-5r5vx`) found correct K=1
provenance and member movement but rejected invariant post-shaping means. A
code audit showed that assertion targeted the wrong layer. K changes the
component simulator's ordinal copula; the full-coverage TabPFN shaper then
replaces each player's marginal from the same key-addressed quantile cache.
Post-shaping player means should therefore remain fixed while joint lineup
worlds change. The audit was corrected without changing any score criterion,
and a regression test covers this invariant. Cloud Build
`a8ed72ec-d909-447f-881e-3eeaca6b2e7f` passed 621 tests (2 skipped) and built
reporting digest `sha256:5b7e8e38399c29315a11a8c13c4c2453dc15042c06ed5c29e45b67ac37ebe712`.

Corrected comparator `compare-adoption-panel-6kf7z` passed with no mechanism
failures. All 47,692 offensive rows recorded K=3 member disagreement; K=1
differed from the K=3 member mean by 0.281 points on average; inputs and
non-ensemble seeds matched; and candidate/player mean error stayed below
`2.36e-05`. K=1 improved selected clears **11→16 at 194**, **1→9 at 200**,
mean selected best **173.06→174.55**, and pool oracle **20→24**; it tied at
26 clears at 187. Season-194 deltas were `{2019:+1, 2021:0, 2022:+3,
2023:+3, 2024:-1, 2025:-1}`.

That pattern fails the frozen directional-stability law: only three seasons
are positive (need at least four) and two are negative (allow at most one).
The disposition is therefore `unsupported-neutral`, not adoption. K=1 is a
promising candidate for genuinely independent future confirmation, but the
current K=3 default remains unchanged and no production knob moves.

## Addendum 108 (2026-08-08): A03 salary-floor deletion is active but unsupported-neutral

Fresh A03 panel `20260808-a03-nofloor-c616390` changed only
`MIN_LINEUP_SALARY=0` on deterministic generation digest
`sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`.
It retained K=3, the 45/55 model/market blend, and the fixed `0/0/0/40`
candidate budget. Preflight `replay-a03floor1-smoke-pddht` passed, followed by
successful season executions `replay-a03floor1-2019-cjn9c`,
`replay-a03floor1-2021-tl84k`, `replay-a03floor1-2022-br5km`,
`replay-a03floor1-2023-z8gpc`, `replay-a03floor1-2024-nd7bv`, and
`replay-a03floor1-2025-vcmkx`.

Check execution `accept-replay-panel-pwlzs` passed: 17,514 candidates, all
107 slates, 50,098 unique feature snapshots, no missing candidate slates or
roster players, and candidate/player mean parity within `2.40e-05`. The
salary audit was built in Cloud Build
`eccb96c1-8fbc-420f-ba37-5d90db0790fc` (624 passed, 2 skipped), producing
reporting digest
`sha256:f6cb471cbb50d5aca186e7f318e29f24d46b83c772cac4951a4c0f4f101ceaee`.

Comparator `compare-adoption-panel-2k87b` passed with no mechanism failures.
All registered upstream feature columns were invariant. The source had zero
candidates or selected lineups below $49k; treatment had **3,729 candidates**
and **468 selected lineups** below $49k. Candidate salary minimum moved
$49,000→$34,100 and selected salary minimum moved $49,000→$43,100, so this
was a real support deletion rather than an inert configuration change.

Scoring did not support adoption. The arm tied at **11/107** clears at 194
and **20/107** pool-oracle clears, fell **26→21** at 187, rose **1→3** at 200,
and lowered mean selected best **173.06→172.43**. Season-194 deltas were
`{2019:0, 2021:0, 2022:0, 2023:+1, 2024:0, 2025:-1}`. It therefore failed
the frozen improvement gate and received `unsupported-neutral`. Retain the
$49k floor. This negative result does not authorize retrospective tuning to
$47,500 or another intermediate floor; that would require independent data
and a fresh preregistration.

## Addendum 109 (2026-08-08): 80-entry tail objective and missed-winner audit

The operator clarified before this analysis that weekly portfolio maximum and
exceptional realized scores matter more than average lineup score, with 80
entries more likely than 40. Production-faithful frozen-mask reconstruction
had zero mismatches for both K=3 and K=1 at 40 entries.

Selecting 80 from the immutable 40-entry candidate pools produced K=3/K=1
counts of **18/22 at 194**, **7/15 at 200**, and **3/9 at 210**. K=1's 200
lift was positive in four seasons, negative in none, and neutral in two. The
full selection-line grid did not produce this conclusion by threshold mining:
194 selection tied the best K=3 high-tail counts and was best/tied-best for
K=1 through 210.

Eighty entries reduced pool-oracle misses at 200 to one week in each model.
K=3 buried its 2023-week-3 winner at simulated probability rank 144/159; its
48.46-point Keenan Allen result was a 30.61-point surprise. K=1's remaining
2019-week-6 winner ranked a plausible 53/161 and could replace one selected
entry without losing final simulated coverage, exposing non-unique greedy
coverage rather than a hindsight-identifiable rule. See
`reports/2026-08-08-80-entry-tail-audit.md` for the full grid and roster
contrasts.

The deeper frontier check reinforces that conclusion. K=3's oracle ranked
25th/30th/26th by probability/mean/q99 among 32 free-swap candidates; a
pre-lock lexicographic one-swap hill climb raised coverage 1,795→1,797 worlds
but still missed it. K=1's oracle ranked a more plausible 4th/10th/4th among
24, yet the same deterministic refinement raised coverage 3,595→3,598 and
also selected other candidates. Neither refinement improved the realized
weekly maximum. The K=1 miss therefore does not expose a simple local-search
fix even though its hindsight winner looks less buried.

This is discovery evidence, not adoption. Candidate generation starts with
`CAND_MULT * n_entries`, so a real 80-entry replay produces 160 rather than 80
leverage candidates. A preregistered same-image K=3/K=1 80-entry pair is next;
its primary high-tail gate is >=200 with the standing 4-positive/<=1-negative
season law, plus non-worsening checks at 194/210 and full mechanism audits.

Before any realized true-80 scores were queried, a cross-model allocation
diagnostic was also preregistered. It will report K=1/K=3 splits of 0/80,
20/60, 40/40, 60/20, and 80/0 using the unchanged 194 coverage selector
inside each model's production-faithful pool. The 40/40 split is the primary
hypothesis and must beat the stronger homogeneous endpoint by at least two
>=200 weeks with the same 4-positive/<=1-negative season law and the existing
194/210/oracle/mean safeguards. Cross-book duplicate rosters will be reported
and retained in historical maximum scoring, so they cannot manufacture an
improvement. Full protocol is in the 80-entry tail audit.

## Addendum 110 (2026-08-08): true-80 K=1 wins aggregate tail but fails stability; mixed book fails

Production-faithful 80-entry panels completed on generation digest
`sha256:98a31edd...`, with 25,813 K=3 and 25,787 K=1 candidates over all 107
slates and exactly 80 selected per slate. Full acceptance and artifact audits
passed; K=3 was promoted as the valid control.

At the preregistered 194 selection line, K=3/K=1 scored **19/22 at 194**,
**8/12 at 200**, **5/6 at 210**, and **1/3 at 220**, with mean weekly maxima
177.08/179.60. K=1's aggregate improvement is real, but its >=200 season
deltas are `{2019:+3, 2021:-1, 2022:+2, 2023:-1, 2024:0, 2025:+1}`: only
three positive seasons and two negative. At 194 it has four positive but still
two negative. Official mechanism comparator `compare-adoption-panel-x9tsz`
had zero failures, but both stability gates fail. K=1 remains
`unsupported-neutral`; K=3 remains the incumbent without weakening the law.

The preregistered 40/40 K=1/K=3 book also failed, with 9 weeks >=200 versus
K=1's 12 and three negative seasons. The 20/60 sensitivity tied K=1 at 12 and
rose to 7 at 210, but it was not the primary hypothesis and improves only
three seasons versus K=3. It is not selected post hoc. Duplicate cross-book
rosters are common (392 slots across 96 slates at 40/40), so any future mixed
implementation also needs deterministic backfill.

The true-80 pools expose a larger selector frontier: K=3 leaves 4 recoverable
>=200 weeks and K=1 leaves 7. Outcome-blind lexicographic one-swap refinement
recovers none of them, including the two K=1 misses with non-worsening oracle
swaps. This strengthens the conclusion that there is no obvious greedy repair
using current beliefs. Full grids, missed rosters, and the 107-row weekly-max
file are in `reports/2026-08-08-80-entry-tail-audit.md` and
`reports/2026-08-08-true80-weekly-max.csv`.

The next arm is now preregistered on reporting/generation digest
`sha256:458dd21d...`: same-image true-80 K=3 averaged-world control versus K=3
coherent member-sampled worlds (`ENSEMBLE_WORLD_MODE=member_sample`, seed
8161). It keeps the 194 selector and the same >=200 4-positive/<=1-negative
law. Its mechanism gate must prove invariant player marginals and inputs but
changed joint support/candidate portfolios before any score is interpreted.

## Addendum 111 (2026-08-08): missed winners are not simulated-support duplicates

The true-80 missed-winner audit now identifies each oracle's nearest selected
substitute in simulated >=194-world support. Across all four K=3 and seven
K=1 consequential >=200 misses, **zero** selected lineups are support
supersets of the oracle and every selected lineup owns at least one unique
world. Nearest-support Jaccard overlap is only 0.228-0.404 for K=3 and
0.140-0.464 for K=1, even though many nearest substitutes share seven of nine
players.

This rejects a simple duplicate-pruning explanation. Some misses are narrow
player-combination errors inside similar rosters (for example RB/DST swaps);
others are different game constructions whose realized booms were not close
in the simulated joint tail. Only two K=1 oracles permit a non-worsening final
coverage swap, and the already-frozen outcome-blind local refinement selects
other candidates. Production selection remains unchanged. The new
diagnostic is covered by the focused tail-portfolio suite and is recorded in
`reports/2026-08-08-80-entry-tail-audit.md`.

Complete validation also passed in Cloud Build
`8b8ba490-a181-408b-bba0-a13a36b69790`: 638 tests passed and 2 skipped,
producing immutable audit-tooling digest
`sha256:c591980dd60244cad370d4e6f8a97fc10de3f7e312760b4bc8ffcafdcfad3f22`.

## Addendum 112 (2026-08-08): coherent ensemble-member worlds are valid but lose the high tail

The preregistered true-80 pair completed with 25,813 candidates and exact 80
selections on every one of 107 slates in each arm. Control check/promotion
executions `accept-replay-panel-jcx6k` / `accept-replay-panel-wkxsd` and
treatment check `accept-replay-panel-b4tqk` all passed. Comparator
`compare-adoption-panel-hz7f7` had zero mechanism failures: 24,118 support
masks, 3,545 candidate rosters, and 2,100 selected slots per side changed,
while every registered invariant input/marginal matched.

At the frozen 194 selector, member-sampled worlds moved 187 clears 29→32,
194 clears 19→20, and mean weekly maximum 177.08→177.94, but reduced the
primary high tail **8→6 at 200** and **5→4 at 210**. The >=200 season deltas
are `{2019:-1, 2021:0, 2022:0, 2023:0, 2024:-1, 2025:0}`. Pool oracle remains
12. The arm fails aggregate lift, stability, and 210 safeguards and receives
`unsupported-neutral`; it stays off.

The two lost weeks are selection losses under changed joint support, not
candidate absence. The 2019w15 control's 204.66 roster remains in treatment
with almost identical probability/mean, while treatment also contains an
unselected 207.14 oracle. The exact 2024w5 211.12 control winner remains the
treatment pool oracle with unchanged marginal probability and mean but is not
selected. Treatment has six consequential >=200 misses versus control's four;
outcome-blind one-swap refinement recovers none. Full threshold and
support-substitute evidence is in `reports/2026-08-08-80-entry-tail-audit.md`.

## Addendum 113 (2026-08-08): candidate-budget doubling preregistered as the final historical confirmation

Before launching or reading any treatment outcomes, one low-prior true-80
candidate-scaling arm is frozen. Accepted same-image source
`20260808-e80-msctl-d99b125` remains the control. Treatment
`20260808-e80-cm4-d99b125` changes only `CAND_MULT=4` from default 2 on the
same generation digest/code, retaining K=3, 194 selection, 80 entries,
45/55 blend, $49k floor, possession mode, all seeds, and fixed `0/0/0/40`
generator budgets.

The mechanism gate requires a strict frozen-world candidate superset on every
slate, extra leverage candidates, invariant shared-roster support/probability/
mean/actual, identical feature snapshots/seeds, and changed selected rosters.
The score gate remains >=2 additional 200+ weeks, >=4 positive and <=1
negative seasons, with 194/210/oracle/mean safeguards. Dose 4 is a single
natural doubling, not a sweep; failure closes raw budget scaling rather than
authorizing 3/5/8 or another target line. The older 470-candidate null and the
current unchanged 12-week pool oracle make this a final confirmation, not the
leading hypothesis.

Operational amendment before outcomes: preflight passed, but observed
14-16-minute first-slate throughput made the runner's inherited three-hour
timeout mechanically insufficient for a full season. The six first season
executions were cancelled before score inspection, and 1,610 partial
candidate plus 2,406 feature rows were transactionally deleted. The same
panel was relaunched on the same immutable image, four CPUs, 16 GiB, seeds,
args, and `CAND_MULT=4`, changing only task timeout to six hours. Immutable
current and superseded execution IDs are tracked in the panel manifest.

## Addendum 114 (2026-08-09): ranked hedges do not repair the missed high scores

Before interpreting selector misses, the corrected true-80 book was compared
with all 68 known same-week Milly winning scores. K=3 beats 0/68, is within 20
points in 0, within 30 in 2, and within 40 in 7; mean gap is 60.69. Its
candidate-pool oracle also beats 0/68 and has mean gap 57.69. K=1 beats 0 and
is within 20 in 0, with selected mean gap 57.16. Fixed 194/200 thresholds
remain useful comparative markers, but cannot be represented as top-prize
proxies. The roughly 58-point oracle gap makes upstream belief/candidate
quality—not selector mining—the dominant first-place problem.

The complete weekly-oracle, coverage-cost, ranked/hybrid, and real-winning-
line audit layer passed Cloud Build `9a33319b-db99-4f4d-95ae-58016db7382f`
(643 passed, 2 skipped), producing immutable digest
`sha256:21489a693a72cb533551e9603db60b53af2fe3e8867fd788e6cac96a304cac59`.

The accepted K=3 true-80 book has 16 unselected candidate rows scoring at
least 200, but ten are redundant to a different selected 200+ lineup on the
same slate. Only six candidate rows across four weeks represent a lost
threshold opportunity. This distinction prevents impressive unselected raw
scores from overstating the actionable gap.

The broader weekly-maximum view selects the exact pool oracle on 74/107
slates and omits it on 33. Omitted-oracle regret has median 6.36 and maximum
35.52, versus 2.72 mean regret over all slates. Five omitted oracles score at
least 200: the four new-threshold opportunities plus 2019 week 15, whose
207.14 improves selected 204.66 by 2.48 but does not add a 200+ week. The
durable analyzer now reports this explicitly rather than hiding it behind
threshold counts.

Only 7/33 omitted weekly oracles have a non-worsening one-for-one coverage
swap, and none of the five omitted 200+ oracles do. Even the small 2019-week-15
upgrade costs six covered worlds. The high omissions are therefore real
belief/portfolio tradeoffs rather than equivalent greedy tie outcomes.

Outcome-blind top-80 selection by individual p-line, simulated mean, or q99
each recovers the 2019-week-6 and 2025-week-12 missed winners. All three still
fall from 8 to 7 aggregate 200+ weeks versus correlated-world coverage and
worsen the lower-tail/mean safeguards. A 60/20 coverage/top-p-line hedge ties
at eight 200+ weeks and improves 210+ from 5 to 6, but drops 194+ from 19 to
18; the simulated-mean hedge is essentially an exact aggregate tie. These
rules exchange winning weeks rather than adding them.

K=1 sensitivities make the panel-mining risk explicit. Top-p-line reaches 15
weeks at 200 and 8 at 210, and 60 coverage plus 20 mean-ranked entries reaches
14/7, but every variant remains positive in only three seasons and negative
in two versus K=3. The aggregate gain is still concentrated in the same
seasons that caused K=1 to fail its frozen stability law.

On paired weeks, preregistered K=1 coverage gains seven 200+ outcomes and
loses three against K=3 (one-sided exact sign-test `p=0.172`). The post-result
top-p-line book gains eleven and loses four (`p=0.059` uncorrected), but that
book was found among multiple selector sensitivities. The latter may be
frozen as a future prospective shadow; it cannot retroactively weaken the
historical stability gate.

No selector change is adopted. The two moderately ranked misses can be found
by marginal ranking only by surrendering other high weeks; the remaining
2019-week-9 and 2021-week-11 winners are deeply buried by every persisted
pre-lock rank and require new information or better beliefs. Reusable
`--ranked-diagnostics` tooling and nine focused tests are now tracked; full
evidence remains in `reports/2026-08-08-80-entry-tail-audit.md`.

The missed winners also fail a simple contrarian-shape explanation. Their
naive pre-lock ownership products sit at the 78.8th-95.0th percentiles of the
80 selected entries on those slates, and each is more popular by proxy than
the selected-best lineup. They span five or six games with no more than four
players from one game. Because historical full classic fields are absent,
this cannot establish actual duplication or payout; it does establish that
the misses are not obviously low-owned, uniquely structured entries worth
forcing into the book.

The new diagnostic layer passed full Cloud Build
`b24be18a-13c8-4912-b324-04d872981ebe` with 643 tests passed and 2 skipped,
producing immutable digest
`sha256:805a7c1e4e8bfdcf088bc0c4a169ef31196a9a35f88e68c58f24a9bbe91ce5f0`.

## Addendum 115 (2026-08-09): learned conditional templates improve average dependence but fail the joint-tail gate

The missed-winner review motivated one new upstream mechanism rather than
another selector sweep: an MMD-style random-feature forest learned
walk-forward weights over fixed-role historical game templates, then imposed
their ranks on the unchanged production marginals. The complete algorithm,
seed, dimensions, 2023-2025 seasons, and two-metric gate were frozen before
any diagnostic result. Cloud Build `107a8e47-1a31-4dc6-a7b8-5d95562bdb60`
passed 650 tests (2 skipped); immutable digest is
`sha256:12cdf18151af051ac766e302514cceaf34c3d9cf320d13bd1467ed8e88e96978`.

All three dependence-only executions completed cleanly with exact marginal
multisets and complete role pairs. The forest improved variogram error in
2023, 2024, and 2025, moving the pair-weighted aggregate
**0.168911→0.165064**. It did not improve the metric most directly tied to
simultaneous high scores: joint-q90 tail Brier worsened slightly
**0.017582→0.017635**, with both metrics improving only in 2023. The frozen
gate therefore fails. The mechanism is active and scientifically valid, but
does not proceed to candidate-oracle or scoring stages. Its hyperparameters,
roles, features, and seasons will not be tuned on this result.

## Addendum 116 (2026-08-09): real-winner exposure is broad, but corrected assembly is not below random

The accepted true-80 K=3 panel was joined to all 68 known same-week Milly
winner rosters, resolving 612 player slots against each immutable slate
snapshot. The pool contains an average 8.51/9 winning players somewhere and
all nine in 39/68 weeks; the selected book contains 8.43 and all nine in 35.
No exact winning roster is present. The closest single candidate contains
3.46 winner players in the pool and 3.31 in the selected book, while the
actual weekly oracle/selected-best contain only 2.07/1.97.

Unlike the superseded old-panel assembly finding, the corrected true-80 book
does not fall below an exposure-preserving null. Holding each winner player's
marginal exposure fixed, independent random assembly produces mean maximum
overlap 3.30 for the candidate pool and 3.22 for the selected book, below the
observed 3.46/3.31. Observed versus null winner-pair occurrence is
0.368/0.366 in the pool and 0.325/0.330 in selection. The null is not a legal
lineup generator, but it falsifies a generic claim that the current generator
systematically scatters winner players that its own exposures already favor.

Only 33/612 winner slots are absent from every candidate, across 29 weeks.
They average 22.74 actual versus 7.19 projected points (+15.55 surprise) and
are concentrated at WR/TE (13/10, plus 7 RB, 2 QB, 1 DST). The remaining
first-place gap is therefore dominated by pre-lock belief on rare individual
and joint booms, not a free assembly or selector repair. Reusable
`real_winner_overlap.py` tooling is wired into the tail analyzer; no lever is
adopted from this outcome-aware diagnostic.

The rejected K=1 panel has nearly identical individual coverage (8.50/9;
34 missing slots), but modestly higher closest-roster overlap: pool 3.53 and
selected 3.44, versus K=3's 3.46/3.31. Its realized oracle/selected-best
overlap rises 2.07→2.31 and 1.97→2.24; the selected-best paired weeks are
25 gains, 27 ties, 16 losses. K=1 remains above its exposure null as well.
This descriptive combination signal supports only the already-declared 2026
prospective shadow; it does not override the frozen season-stability failure.
Full validation passed Cloud Build
`3469c6ad-06fa-4058-8287-f8d4adecc81e` (652 passed, 2 skipped), producing
immutable audit digest
`sha256:81b9faa89829bc5035fdb135e9df8c39ed0f74b5f8ddc6ee5f5dcf2e29950a4a`.

## Addendum 117 (2026-08-09): raw candidate doubling finds opportunities but damages the selected extreme tail

The final registered historical confirmation doubled only `CAND_MULT` from 2
to 4 at true 80, K=3, and frozen selector 194. Treatment
`20260808-e80-cm4-d99b125` completed 42,706 candidates and exactly 8,560
selected rows. Candidate-budget comparator `compare-adoption-panel-ljdlp`
proved a strict superset on all 107 slates: the 25,813 control rows are exact,
16,893 leverage rows are new, every shared belief/support/actual value and
upstream feature is invariant, and 1,832 selected slots move each way.

The larger pool raises 187/194/200 from 29/19/8 to 30/22/9 and mean weekly
maximum 177.08→177.27, but collapses 210 from 5 to 2 while leaving
220/230/240 at 1/1/1. Thus both the originally frozen scientific rule and the
newly prospective tail-first operator rule reject it. The treatment is not
promoted, and another candidate multiple or historical target line will not
be tuned.

The apparent opportunity gain is real but not selectable under current
beliefs. Pool-oracle 200+ weeks rise 12→16, yet seven 200+ weekly oracles are
missed by the 80-entry book. Only one has a non-worsening coverage swap and
the pre-lock local refinement still does not take it. Fifty-five unselected
200+ candidates span 14 slates, but most are redundant on weeks already won
by a higher selected lineup. Top-mean and selector-187 sensitivities reach at
most 10 200+ weeks, below K=1's 12, and are now outcome-viewed.

All four newly created 200+ pool opportunities are extra leverage rosters and
all remain unselected (213.58, 210.64, 202.74, 202.50). The sole selected
200+ gain, 2021w11 at 205.20, already existed in the control pool. Coverage
reshuffling selects it only while displacing three control 210+ weekly
winners. This directly separates a successful opportunity generator from an
unsuccessful submitted-portfolio tail: raw presence is no longer the primary
constraint on these weeks.

Real-winner coverage is likewise nearly unchanged: 8.51/9 winning players
appear somewhere, the same 33/612 slots are absent, closest candidate overlap
improves only 3.46→3.57, and selected overlap stays 3.31. The experiment
closes raw pool scaling and reinforces the next direction: develop K=1 under
the operator's prospective aggregate-tail utility and improve rare-boom
belief/field information rather than spend more compute on candidate volume.

The multiplier-aware acceptance repair and dual-disposition reporting passed
Cloud Build `0cba47ea-954e-451e-b481-f93585d4b593` (657 passed, 2 skipped),
producing digest
`sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`.
Check-only acceptance `accept-replay-panel-z5ncj` passed; the treatment stays
in staging.

## Addendum 118 (2026-08-09): K=1 promoted for the operator's aggregate-tail utility

The operator explicitly accepted individual-season declines when the total
book produces more exceptional weekly highs. Under that utility, true-80 K=1
`20260808-e80-k1-c616390` is the strongest validated historical portfolio:
at the frozen 194 selector it records **36/22/12/6/3/1/1** weeks at or above
187/194/200/210/220/230/240, versus K=3's **29/19/8/5/1/1/1**, while mean
weekly maximum rises 177.08→179.60 and pool-oracle 200+ rises 12→19.

This does not rewrite the earlier preregistered stability disposition. It is
a separate operator-policy decision made after that result, and K=3 remains
the production/stability reference. Canonical acceptance promotion
`accept-replay-panel-jhcwr` passed on validated digest
`sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`,
promoting 25,787 candidates and 50,098 player snapshots across all 107 slates
with exact 80-entry completeness and no parity failures. The next evidence
must be prospective: train and store K=1 in an isolated registry and freeze
Sunday-main candidate books before outcomes without changing the K=3 live
default.

## Addendum 119 (2026-08-09): paired prospective K=1/K=3 shadows are isolated and deployed

The tail-first research baseline now has a fail-closed prospective path and a
same-time canonical reference.
Canonical registry labels remain unchanged; K=1 training writes only
`comp_*__tail_k1`, and shadow loading verifies both the namespace and the
stored member count before any lineup work. `nfl-dfs shadow-k1` selects the
largest all-Sunday DK group only when its Eastern date exactly matches the
next regular-season week's Sunday, then freezes exactly 80 entries at line
194 with the historical 0/0/0/40 generation budget, $49k floor, 45/55 blend,
and user notes disabled. Candidate/player writes and full score-matrix storage
are synchronous and required; any missing artifact, partial portfolio, or
warehouse failure fails the execution.

`nfl-dfs shadow-k3` applies the identical frozen portfolio, date, and storage
contract to canonical K=3, recording `live-shadow-tail_k3-*` separately from
K=1's `live-shadow-tail_k1-*`. This is necessary attribution infrastructure:
an isolated K=1 score cannot show whether the same pre-lock week improved or
declined versus K=3.

Final Cloud Build `a97781f2-c764-4067-b578-feacf931f03c` passed 668 tests (2
skipped), producing immutable digest
`sha256:939778e31defe13dc48b6410d3621422070864cbc60f7fd9680e1faf0d555b89`.
Jobs `train-weekly-k1`, `shadow-k1`, and `shadow-k3` are pinned to that digest.
Training smoke `train-weekly-k1-hrhl8` created
`comp_targets__tail_k1/2026-W32`; the canonical target registry stayed at
2026-W32 with exact before/after listing checksum
`e85a892e48da1b31eb87712b1ace96ea8f8c25f841d9bcdca9084a29b6cd1a8d`.
Schedulers `s-train-k1`, `s-shadow-k1-early`, `s-shadow-k1-late`,
`s-shadow-k3-early`, and `s-shadow-k3-late` are all PAUSED until the August 24
season-start runbook. No live app default or canonical K=3 model was changed.

## Addendum 120 (2026-08-09): corrected K=1 CE and contest-aware ownership paths preregistered

Development resumed after a context compaction incorrectly treated paused
prospective schedulers as a pause in historical research. Cloud execution
history proves there is no unharvested scoring job: the final six no-floor
seasons, acceptance, and salary comparator all completed; the concurrent
Odds API shadow/telemetry work also completed. The next two bounded scoring
paths are now frozen before new results.

First, CE receives its one allowed corrected-universe K=1 confirmation. A
12-CE/40-boom union diagnostic must add at least two 200+ candidate-oracle
weeks before the already-frozen 12-CE/28-boom equal-budget replacement may
run. Both use the accepted true-80 K=1 image/configuration and seed 1701; no
CE parameter or selector tuning is permitted. Exact protocol:
`reports/2026-08-09-k1-ce-true80-experiment.md`.

Second, the existing ownership data will be used through a genuinely
different target, not by repeating the failed generic booster. The current
training target averages incompatible cash/GPP, Classic/Showdown, and slate
scopes. A walk-forward model will instead target the large-field Sunday-main
Milly ownership and use the immutable accepted K=1 Sunday-main snapshots.
Only a preregistered held-out ownership-calibration pass can earn one fixed
K=1 lineup arm; otherwise the path closes without querying lineup outcomes.
Exact protocol: `reports/2026-08-09-milly-ownership-alternative.md`.

## Addendum 121 (2026-10-03): CORRECTION — `xfp_l4` leaked week-W information in training; every XFP verdict is VOID

Found by the B4 outcome-blind audit (`reports/2026-10-03-b4-audit-d1-overlap-map.md`) and CONFIRMED by the reviewer's
code audit.
- **The mechanism:**
  - `sql/features/017j_xfp_schedule.sql` writes one `player_week_xfp` row per (player, week) ONLY when the player had
    at least 1 target (with air yards) or 1 carry THAT week. `xfp_l4` is the mean of the previous four such rows,
    so the value itself is prior-only.
  - `021_player_week_training.sql` joins it by the EXACT week (`xf.week = u.week`). A training row therefore has a
    non-NULL `xfp_l4` only if the player got an opportunity in the very game being predicted. NULL encodes "zero
    targets or carries in week W", which is post-game information a tree model learns.
- **Train and serve differ:** `023_player_week_inference.sql` takes the latest row instead, so live NULL means "no
  prior opportunity" and live values are one game stale (W3/W4: 211/222 and 267/281 values differ).
- **Consequence:** the XFP arm ("positive alone; stays candidate", the August candidate panel) and the XFP component
  of XSCHED measured a leaked feature. Those verdicts are **VOID until re-run on a fixed feature**. SCHED's adoption
  is unaffected (SCHED alone = XSCHED).
- **Production:** none. `xfp_l4` is in `CANDIDATE_FEATURES` only, and no live job sets `EXTRA_FEATURES`.
- **Fix design** (reviewer): build xfp on a player-week spine (xfp = 0 for active zero-opportunity weeks), with
  windows over weeks ending `1 PRECEDING`. Live uses the same window ending at the latest played week. Add `xfp_l4`
  to the leakage suite with `require_null_parity=True`. Sweep the other exact-week joins for the same class. The
  register entry is OPEN-DEFECTS O-21.


## Addendum 122 (2026-10-05): study 1 (de-concentration) — NO DIFFERENCE; the transfer check shows no benefit on the real 2026 contests

**Setup.**
- Preregistration: `reports/2026-10-05-prereg-study1-deconcentration.md`, frozen at `e7f5a36a`, with deviation notes
  1–5: the LAG-only term at 0.10; banks 1402/1403; the DST counting fix; the stopped run with 2 rows deleted unread.
- Panel: L13's 36 slates (2023–24), fresh banks 1402/1403, the L-series builder at K = 105.
- Arms:
  - C, the current capped sequential optimizer;
  - G, a per-game budget: the share of rows with ≥ 3 players from game g ≤ min(0.5, P(top-3 game | total rank)),
    from 2014–21 outcomes;
  - P4, offset dealing (`ENTER_LAYOUT=spread`);
  - G+P4.
- Reader frozen before any scored bank: sha256 `21f364d3…bcc59`.

**Reader output (verbatim):**
```
STUDY 1 READER  sha256 21f364d36fb21989ce8e2ff7f7aa7c5e06fd2d591c7fd5e1ebbc16b2257bcc59
DIRECTION: pct = share of the sampled field a row BEATS (higher = better); every difference is ARM - C; POSITIVE favours the arm.
slates 36  banks [1402, 1403]  B 20000  seed 20261005  each interval 0.99167 (family 0.975)

== PRIMARY plan: contests.json  (22 mean-track contests, 147 entries)
G vs C (row level): -0.00345  [-0.02428, +0.01741]  seasons 2023 -0.01925, 2024 +0.01236  tickets 328.0 vs 314.0 (+4.5%)  zero-ticket slates 0.236 vs 0.319  ->  NO DIFFERENCE
P4 vs C (entry level): -0.00553  [-0.01815, +0.00764]  seasons 2023 -0.00436, 2024 -0.00670  tickets 288.0 vs 314.0 (-8.3%)  zero-ticket slates 0.194 vs 0.319  ->  NO DIFFERENCE (a secondary tolerance fails)
G+P4 vs C (entry level): -0.00920  [-0.03485, +0.01555]  seasons 2023 -0.02491, 2024 +0.00650  tickets 306.0 vs 314.0 (-2.5%)  zero-ticket slates 0.167 vs 0.319  ->  NO DIFFERENCE
secondaries:
  C    entry pct mean 0.53350  worst-decile slate 0.34684  bust exposure 0.0719
  G    entry pct mean 0.53527  worst-decile slate 0.37481  bust exposure 0.0803
  P4   entry pct mean 0.52797  worst-decile slate 0.33528  bust exposure 0.0712
  GP4  entry pct mean 0.52430  worst-decile slate 0.34846  bust exposure 0.0785
  G75  entry pct mean 0.53088  worst-decile slate 0.35435  bust exposure 0.0787
  C    row pct mean 0.52948  best>=194 0.292  best>=200 0.153
  G    row pct mean 0.52603  best>=194 0.250  best>=200 0.153
  G75  row pct mean 0.52065  best>=194 0.278  best>=200 0.139   (EXPLORATORY, not decision-bearing)
[then rc 1 on the sensitivity plan: "head: the plan needs rank 105 but the book has 105 rows" — the routed W3 plan
 needs K 106 against the panel's 105; the sensitivity is UNAVAILABLE AS FROZEN and was not patched]
```

**Transfer check** (descriptive; the current system A1 vs A1 + `--main-game-cap p3` on the real 2026 W1–4 pools, scored
by the money-gate harness's validated scorer):
```
STUDY-1 TRANSFER CHECK (descriptive): AG - A1 on the real 2026 W1-4 contests; higher pct = better; W4 motivated the study
book sha: {'A1': {1: '6debe475', 2: 'bf1a5438', 3: 'f08e6bad', 4: '010df6c0'}, 'AG': {1: '6debe475', 2: 'bf1a5438', 3: '6e2dadd3', 4: 'a7ce049f'}}
W1: multiple A1 0.850 AG 0.850 | ex-largest A1 0.799 AG 0.799 | cashes 40 vs 40 | mean entry pct 67.6587 vs 67.6587 | contests with no cash 0 vs 0 of 3 | contests AG above/below A1 0/0 | identical book True
W2: multiple A1 0.650 AG 0.650 | ex-largest A1 0.549 AG 0.549 | cashes 9 vs 9 | mean entry pct 36.0494 vs 36.0494 | contests with no cash 7 vs 7 of 12 | contests AG above/below A1 0/0 | identical book True
W3: multiple A1 0.000 AG 0.000 | ex-largest A1 0.000 AG 0.000 | cashes 0 vs 0 | mean entry pct 52.7828 vs 47.7962 | contests with no cash 45 vs 45 of 45 | contests AG above/below A1 0/6 | identical book False
W4 (motivating): multiple A1 0.174 AG 0.174 | ex-largest A1 0.087 AG 0.087 | cashes 2 vs 2 | mean entry pct 44.7242 vs 43.4113 | contests with no cash 23 vs 23 of 25 | contests AG above/below A1 5/3 | identical book False
W1-4: multiple A1 0.484 AG 0.484; ex-largest 0.462 vs 0.462; mean entry pct 49.6721 vs 47.3892
W1-3 (excl. motivating W4): multiple A1 0.565 AG 0.565; ex-largest 0.537 vs 0.537; mean entry pct 51.6461 vs 48.9761
contests AG above / below A1 (W1-4, contest-level, anti-conservative): 5 / 9
```

**Verdict.**
- Every primary is NO DIFFERENCE; P4 also fails the ticket tolerance (−8.3%). Nothing is adopted.
- In the panel the game cap acts as VARIANCE SHAPING:
  - fewer zero-ticket slates (0.319 → 0.236 for G, 0.167 for G+P4);
  - a better worst decile;
  - a slightly lower ceiling (best ≥ 194 0.292 → 0.250);
  - one-player-bust exposure is NOT reduced (0.072 → 0.080).
- On the real 2026 contests the cap does not bind in W1–2. In W3–4 money is unchanged and mean entry finish is lower
  (−5.0, −1.3). The empty-week reduction seen in the panel's secondaries could NOT be tested on the real contests: too
  few cashes (W3 0 of 45 in both arms; W4 the same 2 cashes). The primary finish measure is slightly worse in both the
  panel and the transfer check, so G is not offered.
- **G is not offered, not even as a risk preference.** The Chase-type single-player risk needs the entry-level player
  cap (study 1's original scope), not a game cap.
- **Process lessons** (recorded in HANDOFF):
  - the API mismatch between mocked tests and the pinned lab (`set_constraints` vs `member_bounds`) was caught by
    the transfer build, and now has an AST guard;
  - a frame quirk (DST side ids) was caught by reviewing the NULL-total question before reading any result.

## Addendum 123 (2026-10-05): study 1b (entry-level player cap): EA and EW both FAIL; the cap halves the single-bust swing at a cost of 2.4–4.3 points of mean finish

**Setup.**
- Preregistration: `reports/2026-10-05-prereg-study1b-entry-player-cap.md`, frozen at `3da5d1d1`, with four deviation
  notes:
  1. The operator re-chose the margin at m = 0.015, after seeing the corrected scale.
  2. The EW arms get EA's re-deal pass. The outcome-blind smoke showed that the pre-limit w_k leaked the cap.
  3. The reader was frozen, and the census came in.
  4. The reader was re-frozen, sha `384e62f7…`, with PARTIAL as a flag that carries its numbers.
- Panel: L13's 36 slates, fresh banks 1404/1405, the L-series builder at K 105, the LAG-only term at 0.10, and the
  Week-4 mean-track plan (147 entries).
- Lab code: nfl2 `production/s1b-entry-cap-20261005` (code acea6b9; results 54c3d8d; LEDGER f88f0c6).
- **Reproduced byte-identically by the reviewer:** stdout sha256 `968c4bdf…`.

**Reader output (verbatim):**
```
STUDY 1b READER  sha256 384e62f77acedb71a0d73baf46e0f7ee79c466f5fb9bb0dc8817baf00f465629
DIRECTION: pct = share of the sampled field a row BEATS (higher = better). d2 = ARM - C, POSITIVE favours the arm; d1 = WSB(ARM) - WSB(C), NEGATIVE favours the arm (less single-bust loss).
slates 36  banks [1404, 1405]  B 20000  seed 20261005  one-sided level 0.9875 (family 0.975)  margin 0.015  plan 22 mean-track contests, 147 entries

== EA vs C  [DECISION]
  co-primary 1 WSB  d1 -0.00182  upper -0.00099  seasons 2023 -0.00180, 2024 -0.00184
  co-primary 2 pct  d2 +0.00170  lower -0.00148  (margin -0.015)  seasons 2023 +0.00247, 2024 +0.00092
  dealt identical to C: 0.000 of slate-banks   miss rate 0.3822   realized max above the cap on 72/72 slate-banks (mean excess +42.6, worst +53)
  ->  FAIL  |  THE CAP IS NOT ACHIEVED BY ASSIGNMENT ALONE (miss rate 0.382 > 0.1)  |  PARTIAL (over the cap on 72/72 slate-banks; mean excess +42.6 entries; worst +53)

== EW vs C  [DECISION]
  co-primary 1 WSB  d1 -0.02054  upper -0.01740  seasons 2023 -0.01991, 2024 -0.02117
  co-primary 2 pct  d2 -0.03543  lower -0.07302  (margin -0.015)  seasons 2023 -0.02558, 2024 -0.04527
  dealt identical to C: 0.000 of slate-banks   miss rate 0.0236   realized max above the cap on 49/72 slate-banks (mean excess +2.8, worst +10)
  ->  FAIL (cost: the non-inferiority bound fails)  |  PARTIAL (over the cap on 49/72 slate-banks; mean excess +2.8 entries; worst +10)

== EW25 vs C  [EXPLORATORY (never decision-bearing)]
  co-primary 1 WSB  d1 -0.02444  upper -0.02110  seasons 2023 -0.02370, 2024 -0.02517
  co-primary 2 pct  d2 -0.04308  lower -0.08175  (margin -0.015)  seasons 2023 -0.03660, 2024 -0.04956
  dealt identical to C: 0.000 of slate-banks   miss rate 0.0254   realized max above the cap on 60/72 slate-banks (mean excess +2.7, worst +9)

== EW35 vs C  [EXPLORATORY (never decision-bearing)]
  co-primary 1 WSB  d1 -0.01776  upper -0.01440  seasons 2023 -0.01828, 2024 -0.01723
  co-primary 2 pct  d2 -0.02442  lower -0.05684  (margin -0.015)  seasons 2023 -0.01655, 2024 -0.03228
  dealt identical to C: 0.000 of slate-banks   miss rate 0.0275   realized max above the cap on 54/72 slate-banks (mean excess +3.1, worst +13)

secondaries (slate means; EBL = 0.20 x sum of swings over the slate's swing set, same players for every arm):
  C     entry pct 0.53321  worst-decile slate 0.35343  WSB 0.04452  top-3 0.11311  EBL 0.04170  tickets 314.5  zero-ticket slates 0.319  best>=194 0.264  best>=200 0.167  bust exposure 0.0713  max entry exposure 0.611
  EA    entry pct 0.53491  worst-decile slate 0.34955  WSB 0.04270  top-3 0.10954  EBL 0.04168  tickets 327.0  zero-ticket slates 0.319  best>=194 0.264  best>=200 0.167  bust exposure 0.0716  max entry exposure 0.589
  EW    entry pct 0.49778  worst-decile slate 0.33449  WSB 0.02398  top-3 0.06366  EBL 0.03686  tickets 332.5  zero-ticket slates 0.181  best>=194 0.264  best>=200 0.208  bust exposure 0.0685  max entry exposure 0.318
  EW25  entry pct 0.49013  worst-decile slate 0.32783  WSB 0.02009  top-3 0.05305  EBL 0.03584  tickets 323.0  zero-ticket slates 0.139  best>=194 0.264  best>=200 0.194  bust exposure 0.0662  max entry exposure 0.263
  EW35  entry pct 0.50879  worst-decile slate 0.33370  WSB 0.02677  top-3 0.07145  EBL 0.03769  tickets 344.0  zero-ticket slates 0.125  best>=194 0.250  best>=200 0.222  bust exposure 0.0655  max entry exposure 0.368

realized max player exposure in dealt entries (slate mean over banks; caps EA 44, EW 44, EW25 36, EW35 51):
  slate           C      EA      EW    EW25    EW35
  2023-W01     85.0    82.5    47.5    39.5    54.5
  2023-W02     92.0    88.0    52.5    38.0    51.0
  2023-W03     88.5    85.0    47.5    37.0    53.0
  2023-W04     95.5    91.0    45.0    36.5    52.5
  2023-W05     87.0    86.5    44.5    41.0    51.5
  2023-W06     88.5    85.5    49.5    38.0    53.5
  2023-W07     91.0    75.5    45.0    38.0    54.0
  2023-W08     90.5    88.5    44.5    38.0    52.5
  2023-W09     93.0    85.5    44.5    39.0    55.0
  2023-W10     88.0    83.5    51.5    36.5    57.5
  2023-W11     93.5    85.5    47.0    41.0    59.0
  2023-W12     91.0    92.5    49.0    38.0    53.0
  2023-W13     94.5    90.5    44.0    37.0    52.5
  2023-W14     92.0    90.0    46.0    41.5    53.0
  2023-W15     92.5    93.5    46.0    37.0    51.5
  2023-W16     92.5    89.5    46.0    38.0    51.5
  2023-W17     83.5    81.5    46.0    37.0    52.0
  2023-W18     94.0    95.0    45.0    36.0    51.5
  2024-W01     91.5    84.0    46.0    38.0    55.5
  2024-W02     85.5    79.0    45.5    41.5    54.5
  2024-W03     92.5    90.0    50.0    40.0    58.0
  2024-W04     84.5    82.5    45.5    39.0    57.5
  2024-W05     90.0    90.0    49.0    39.5    55.0
  2024-W06     85.5    84.5    45.5    37.5    51.5
  2024-W07     88.0    85.0    45.5    37.0    57.0
  2024-W08     94.0    92.0    44.0    37.0    51.5
  2024-W09     90.5    85.5    44.0    37.5    53.0
  2024-W10     91.5    86.5    44.0    37.5    54.0
  2024-W11     91.0    90.5    49.5    40.0    57.5
  2024-W12     91.5    89.5    49.0    40.5    53.0
  2024-W13     79.0    77.5    49.5    42.5    61.0
  2024-W14     89.0    90.0    44.5    41.5    55.0
  2024-W15     92.0    88.5    47.5    40.0    54.0
  2024-W16     82.0    82.0    49.5    39.5    51.0
  2024-W17     87.0    88.0    49.5    37.5    55.5
  2024-W18     93.5    84.0    46.5    40.0    55.0
  pooled      0.611   0.589   0.318   0.263   0.368   (share of entries)

SENSITIVITY plan (Week 3 routed): UNAVAILABLE by design -- the deal and the caps are computed in the run with the primary plan only (and study 1 found the Week-3 plan needs 106 rows against K 105).
```

**Transfer check** (descriptive; EA only):
- A1's real books, re-dealt by the lab's frozen assignment cap and scored by the money-gate harness's validated scorer.
  The script is `scripts/moneygate_transfer_s1b.py` @ 93859a19 on `production/moneygate-harness-20261005`.
- EW was not built. It needs an entry-weighted ban mode in `union_reselect`, and it is not an adoption candidate.
```
STUDY-1b TRANSFER CHECK (descriptive): EA - A1 on the real 2026 W1-4 contests; higher pct = better; W4 motivated the study; EW not built (no adoption candidate)
lab rule: /home/erich/projects/.nfl2-worktrees/s1b-entry-cap-20261005  A1 book sha: {1: '6debe475', 2: 'bf1a5438', 3: 'f08e6bad', 4: '010df6c0'}
W1: mean-track entries 23 cap 6 | misses 8 (0.348) | entries changed 11 | max player entries A1 12 EA 11 | multiple A1 0.850 EA 0.850 | ex-largest 0.799 vs 0.799 | cashes 40 vs 39 | mean entry pct 67.6587 vs 67.2668 | contests with no cash 0 vs 0 of 3 | contests EA above/below A1 0/1
W2: mean-track entries 96 cap 28 | misses 38 (0.396) | entries changed 14 | max player entries A1 56 EA 50 | multiple A1 0.650 EA 0.650 | ex-largest 0.549 vs 0.549 | cashes 9 vs 9 | mean entry pct 36.0494 vs 38.1491 | contests with no cash 7 vs 7 of 12 | contests EA above/below A1 4/0
W3: mean-track entries 132 cap 39 | misses 48 (0.364) | entries changed 15 | max player entries A1 79 EA 72 | multiple A1 0.000 EA 0.000 | ex-largest 0.000 vs 0.000 | cashes 0 vs 0 | mean entry pct 52.7828 vs 53.2802 | contests with no cash 45 vs 45 of 45 | contests EA above/below A1 2/0
W4 (motivating): mean-track entries 147 cap 44 | misses 59 (0.401) | entries changed 5 | max player entries A1 93 EA 89 | multiple A1 0.174 EA 0.174 | ex-largest 0.087 vs 0.087 | cashes 2 vs 2 | mean entry pct 44.7242 vs 44.7636 | contests with no cash 23 vs 23 of 25 | contests EA above/below A1 1/0
W1-4: multiple A1 0.484 EA 0.484; ex-largest 0.462 vs 0.462; mean entry pct 49.6721 vs 50.1970; misses 153/398
W1-3 (excl. motivating W4): multiple A1 0.565 EA 0.565; ex-largest 0.537 vs 0.537; mean entry pct 51.6461 vs 52.3647; misses 94/251
contests EA above / below A1 (W1-4, contest-level, anti-conservative): 7 / 1
```

**Verdicts (frozen rule):**
- **EA FAILS: the cap cannot be achieved by assignment alone.**
  - It misses 38% of entries on every slate-bank, and 153 of 398 on the real 2026 weeks.
  - The most-used player barely moves: from 61% to 59% of entries on the panel, and from 93 to 89 entries in real W4.
- **EW FAILS on cost.**
  - It does what a cap is meant to do. It holds the most-used player at 0.318 of entries against C's 0.611, and it
    roughly halves the worst single-bust swing (WSB 0.0445 → 0.0240; d1 upper −0.0174, both seasons).
  - But it costs 3.5 points of mean entry finish: lower bound −7.3, against the operator's margin of −1.5.
  - Neither the 25% nor the 35% level comes close: d2 is −4.3 and −2.4.

**What the secondaries suggest (NOT evidence):**
- De-concentration LOWERED mean entry finish but RAISED line-crossings:
  - tickets: 314.5 for C against 332.5 for EW and 344.0 for EW35;
  - zero-ticket slates: 0.319 against 0.181 and 0.125;
  - best ≥ 200: 0.167 against 0.208 and 0.222.
- Study 1's G moved the same way (zero-ticket slates 0.319 → 0.236).
- That is the correlation trade: less correlated entries cross high lines more often, at a lower average.
- These numbers come from 5 arms with no intervals. They motivate a NEW preregistration (study list item 14), with
  tickets and line-crossings by contest class as the primary and mean finish as the guard. They support no adoption.
- The winners study found concentration +EV at the satellite lines, so the new test must be able to come out either way.

**No adoption.** The per-contest row cap stays as it is. The operator's question, whether we should hold any one player
under about a third of entries, is answered: not at the cost the panel measures on mean finish. Whether it pays at the
lines is the next study.

## Addendum 124 (2026-10-05): study 15 (a looser QB stack): S1 and S1HT both NO DIFFERENCE

**Setup.**
- Preregistration: `reports/2026-10-05-prereg-study15-qb-stack.md`, frozen at `78ab9a95`, with deviation note 1 (the
  reader frozen at sha `817574f7…`, plus the census).
- The operator's request: "only a QB, 1 WR and a bring back is sufficient for a game we expect to be a shootout".
- Arms:
  - C, the live QB + 2 WR/TE + bring-back;
  - S1, QB + 1 everywhere;
  - S1HT, QB + 1 only for teams in the slate's top-2-total games, through the lab's new `TeamStackRules`.
- Panel: L13's 36 slates, banks 1407/1408, K 105, LAG 0.10, the Week-4 plan.
- Lab: nfl2 `production/s15-qb-stack-20261005` (code `7d2bd02`, results `044799f`, LEDGER `1e3e07e`).
- **Reproduced byte-identically by the reviewer:** stdout sha256 `732525c9…`.

**Reader output (verbatim):**
```
STUDY 15 READER  sha256 817574f7961e0154a0619d208ea021338b283320812a1c431df644047d18c0be
DIRECTION: pct = share of the sampled field a row BEATS (higher = better); every difference is ARM - C; POSITIVE favours the arm.
slates 36  banks [1407, 1408]  B 20000  seed 20261005  each interval 0.9750 two-sided (family 0.975)  plan 22 mean-track contests, 147 entries

== S1 vs C
  PRIMARY mean entry pct  +0.00744  [-0.01317, +0.02822]  seasons 2023 -0.01491, 2024 +0.02978
  GUARD tickets per slate -1.181  [-3.472, +1.070]   best>=200 -0.0139  [-0.1111, +0.0833]
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE -- to the operator: no measurable effect; switching is your preference, reversible, with the rollback

== S1HT vs C
  PRIMARY mean entry pct  -0.00367  [-0.02656, +0.01977]  seasons 2023 -0.01595, 2024 +0.00862
  GUARD tickets per slate +0.042  [-2.056, +2.097]   best>=200 +0.0139  [-0.0694, +0.0972]
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE -- to the operator: no measurable effect; switching is your preference, reversible, with the rollback

secondaries (slate means):
  C     entry pct 0.53490  worst-decile slate 0.34047  tickets 325.5  zero-ticket slates 0.264  best>=194 0.319  best>=200 0.139  pred-own sum 62.19  max entry exposure 0.606
        stack shape: rows with 1 / 2 / 3+ same-team catchers 0.000 / 1.000 / 0.000; dealt entries with 1 catcher 0.000; bring-backs per row 1.00
  S1    entry pct 0.54234  worst-decile slate 0.35805  tickets 283.0  zero-ticket slates 0.236  best>=194 0.181  best>=200 0.125  pred-own sum 63.45  max entry exposure 0.618
        stack shape: rows with 1 / 2 / 3+ same-team catchers 0.927 / 0.073 / 0.000; dealt entries with 1 catcher 0.934; bring-backs per row 1.08
  S1HT  entry pct 0.53123  worst-decile slate 0.30963  tickets 327.0  zero-ticket slates 0.292  best>=194 0.250  best>=200 0.153  pred-own sum 63.25  max entry exposure 0.611
        stack shape: rows with 1 / 2 / 3+ same-team catchers 0.654 / 0.346 / 0.000; dealt entries with 1 catcher 0.657; bring-backs per row 1.07
```

**Disclosed reader defect:**
- The frozen text specifies two-sided 0.9875 intervals per arm. The reader used two-sided 0.975: quantiles
  [0.0125, 0.9875]. Its header prints "0.9750".
- A labelled sensitivity copy at 0.9875 (sha `50dce991`, in `results/s15/`) gives the SAME verdicts:
  - S1: primary [−0.01559, +0.03044], tickets [−3.708, +1.347];
  - S1HT: primary [−0.02890, +0.02254], tickets [−2.292, +2.306].
- Widening an interval cannot turn NO DIFFERENCE into PASS, WORSE or NOT OFFERED.
- The frozen reader is not patched. The defect class was swept: s1b and s16 match their texts.
- **Lesson** (for every reader from now on): the tests assert the PRINTED LEVEL against the preregistration's stated
  level, not the constant the code uses.

**Verdicts:**
- **S1, NO DIFFERENCE.** Mean entry finish +0.7 points, inside an interval that straddles 0.
  - It cashed about 13% fewer tickets: 283 against 325.5, n.s.
  - It lost ceiling: best ≥ 194 on 18% of slates against 32%.
- **S1HT, NO DIFFERENCE.** Indistinguishable from today on every measure: tickets 327 against 325.5.
- **To the operator:** "no measurable effect; switching is your preference, reversible, with the rollback".
- **Any offer** needs a NEW lab pin carrying `TeamStackRules`, because the production pin `32cdb61` lacks it, plus a
  `check_lab_api` run before any entry.

## Addendum 125 (2026-10-05): study 16 (the operator's thesis portfolio): NO DIFFERENCE on tickets; the mean-finish guard far below its margin; 16b not pursued

**Setup.**
- Preregistration: `reports/2026-10-05-prereg-study16-thesis-portfolio.md`, frozen at `fa38a7f8`, with four deviation
  notes:
  1. the D'Hondt rank order;
  2. cells (b) and (c) redefined after an outcome-blind smoke showed them infeasible under MAX_PER_GAME 4;
  3. the reader frozen (`04ed4fda`), plus the census;
  4. the EXPLORATORY sleeve SL25, frozen before the read (`758036eb`), after the operator's clarification that the
     thesis is meant as one strategy among several.
- Panel: L13's 36 slates, banks 1409/1410, K 105, LAG 0.10, the Week-4 plan.
- Lab: nfl2 `production/s16-thesis-portfolio-20261005` (results `18433ae`, LEDGER `e153b5d`).
- **Reproduced byte-identically by the reviewer**, both the reader and the sleeve.

**Reader output (verbatim):**
```
STUDY 16 READER  sha256 04ed4fda8d67ccc194bd90165843aeced115aae025edfa22e205996bb0b40b9f
DIRECTION: tickets = dealt entries at or above their contest's line (higher = better); pct = share of the sampled field a row BEATS; every difference is ARM - C; POSITIVE favours the arm.
slates 36  banks [1409, 1410]  B 20000  seed 20261005  primary two-sided 0.975, guard one-sided 0.975 at -0.015  plan 22 mean-track contests, 147 entries

== TP vs C  [DECISION]
  PRIMARY tickets per slate -1.833  [-5.347, +1.431]  seasons 2023 -1.722, 2024 -1.944
  GUARD mean entry pct -0.04316  one-sided lower -0.07687  (must exceed -0.015)
  simulated line-crossing share -0.01083  [-0.01328, -0.00846]  (secondary)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +40% reads NO DIFFERENCE on 36 slates)

== TP10 vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate -1.694  [-5.195, +1.625]  seasons 2023 -1.583, 2024 -1.806
  GUARD mean entry pct -0.04467  one-sided lower -0.07727  (must exceed -0.015)
  simulated line-crossing share -0.01108  [-0.01359, -0.00865]  (secondary)
  dealt identical to C: 0.000 of slate-banks

== TP20 vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate -1.472  [-4.708, +1.597]  seasons 2023 -1.417, 2024 -1.528
  GUARD mean entry pct -0.03800  one-sided lower -0.06938  (must exceed -0.015)
  simulated line-crossing share -0.01050  [-0.01285, -0.00818]  (secondary)
  dealt identical to C: 0.000 of slate-banks

secondaries (slate means):
  C     tickets 326.0  zero-ticket slates 0.306  best>=200 0.181  entry pct 0.53258  worst-decile slate 0.36281  max entry exposure 0.608  simulated crossing 0.11670
  TP    tickets 260.0  zero-ticket slates 0.167  best>=200 0.153  entry pct 0.48942  worst-decile slate 0.29666  max entry exposure 0.594  simulated crossing 0.10587  entries core/mid/blow 0.891/0.068/0.041
  TP10  tickets 265.0  zero-ticket slates 0.236  best>=200 0.139  entry pct 0.48792  worst-decile slate 0.28288  max entry exposure 0.589  simulated crossing 0.10562  entries core/mid/blow 0.934/0.037/0.029
  TP20  tickets 273.0  zero-ticket slates 0.250  best>=200 0.181  entry pct 0.49458  worst-decile slate 0.29608  max entry exposure 0.594  simulated crossing 0.10620  entries core/mid/blow 0.838/0.109/0.054
```

**Sleeve output (verbatim; EXPLORATORY):**
```
STUDY 16 SLEEVE (EXPLORATORY; deviation note 4)  sha256 758036ebbd1942458cb476b38a34ffa7d7b9594277d41301fcfb39b6813273c4
SL25 - C tickets are expected to be about 0.25 x (TP - C): a consistency check on TP, NOT evidence. The sleeve's own content: zero-ticket slates, the per-slate ticket SD, best >= 200, max entry exposure.

slates 36  banks [1409, 1410]  B 20000  seed 20261005  tickets two-sided 0.975; guard one-sided 0.975 at -0.015
SL25 - C tickets per slate -1.208  [-2.472, -0.069]   (consistency check: ~0.25 x TP - C)
SL25 - C mean entry pct -0.01253  one-sided lower -0.03108
  C     tickets 326.0  per-slate ticket SD 12.195  zero-ticket slates 0.306  best>=200 0.181  max entry exposure 0.608  entry pct 0.53258
  SL25  tickets 282.5  per-slate ticket SD 10.957  zero-ticket slates 0.292  best>=200 0.139  max entry exposure 0.717  entry pct 0.52006  sleeve share of entries 0.270 (min 0.248, max 0.344; plan share mean 0.100)
```

**Verdict.**
- **NO DIFFERENCE on tickets (the frozen verdict):** −1.83 per slate [−5.35, +1.43]; tickets 326 → 260.
- **The mean-finish guard, DESCRIPTIVE here** (the frozen reader reaches it only on a tickets PASS), is far below its
  margin: −0.043, one-sided lower −0.077 against −0.015. This clause is not the frozen verdict.
- **The simulated crossing secondary:** −0.011 [−0.013, −0.008], C 0.117 → TP 0.106, about −9% relative against −20% in
  realized tickets. It is in-sample on the books' own worlds, so biased AGAINST TP.
- **Zero-ticket slates fell:** 0.306 → 0.167, the same pattern as studies 1 and 1b.

**Mechanism** (outcome-blind):
- C already deals 75% of entries to QBs from the top-4 totals and 24% to ranks 5–8. TP deals 89% / 7%, plus 4% RB-led
  blowouts.
- TP chose games by the pre-lock Vegas TOTAL rank, the same signal the optimizer already weights. So the thesis as tested
  is a heavier bet on the market's expected shootouts, i.e. MORE chalk-game concentration, not an independent view.
- It cost about 4 points of mean finish per entry.

**SL25** (exploratory; a consistency check, not evidence):
- Tickets −1.21 [−2.47, −0.07], against the pre-stated ≈ s × (TP − C) ≈ 0.27 × −1.83 = −0.49.
- The sleeve replaced C's LAST 26 rows with TP's head rows (89% core). With the caps not re-imposed (as pre-stated), the
  maximum entry exposure rose from 0.608 to 0.717. So the sleeve added correlated exposure to C's core players rather
  than diversifying. Deal re-assignment is a second candidate.
- The run cannot separate the two without a post-hoc decomposition, which was not done.

**No adoption; 16b NOT pursued now.** The per-entry evidence says thesis rows built this way are worse per entry, and
tickets add up per entry.
- **The caveat for the operator:** what was tested is the VEGAS thesis (games A–D = the top-4 totals). His own pick of
  games cannot be tested historically, because no record of his picks exists.
- **The only route, offered as his option and not as a recommendation:** before each Saturday build he names 4 games; a
  PAPER sleeve of thesis rows is built on them (nothing entered); and Monday's unchanged comparison scores it beside the
  book. Several weeks of that are anecdote, not evidence.

**Today's pattern across studies 1, 1b and 16:** every form of spreading the book (by game, by player entry cap, by
scenario) lowered mean entry finish. Several cut zero-ticket slates. None raised expected tickets measurably.

**Addendum 125, note (2026-10-05, later the same day):** the operator-picks paper-sleeve option above is WITHDRAWN. The
operator, verbatim: "I don't want to have to study football, so I don't want to be providing my picks." 16b is TABLED,
pending his reply to the reviewer, for the reason stated above: thesis rows are worse per entry, and tickets add up per
entry.

## Addendum 126 (2026-10-05): study 16c (the thesis with NO contrarian element): NO DIFFERENCE on tickets; the thesis portfolio is closed in both forms

**Setup.**
- The operator asked: "did it include contrarian players? if so, try again without any contrarian element".
  - Player-level contrarian was never an arm.
  - Study 16's 15% mid/blow cells were the game-level contrarian element.
- So TP0 is core only: 100% of rows with the QB's game at total rank ≤ 4, ∝ P3, with the same optimizer, caps, LAG 0.10
  and D'Hondt order, against C.
- Preregistration: `reports/2026-10-05-prereg-study16c-core-only.md`, frozen at `b1e7a0b3` before the census and the
  scored banks (reader sha `ceb90a64`), with deviation note 1 `d0e88cc1` (the census: all core, 0 passes, 0.965 entries
  changed).
- Panel: L13's 36 slates, banks 1411/1412.
- Frozen and read by the reviewer. **Reproduced byte-identically by the laptop**: reader `ceb90a64`; raw banks 1411
  `8162e744`, 1412 `ee2657a2`; READ sha `03dc374b`. Lab: nfl2 `production/s16c-core-only-20261005` (results `c901116`,
  LEDGER `fb57921`).

**Reader output (verbatim):**
```
STUDY 16c READER  sha256 ceb90a64af6179bb0dbe30c285fbdd47c3729125c507cdf7664971385468c766
DIRECTION: tickets = dealt entries at or above their contest's line (higher = better); pct = share of the sampled field a row BEATS; every difference is ARM - C; POSITIVE favours the arm.
slates 36  banks [1411, 1412]  B 20000  seed 20261005  primary two-sided 0.975, guard one-sided 0.975 at -0.015  plan 22 mean-track contests, 147 entries

== TP0 vs C  [DECISION]
  PRIMARY tickets per slate -0.611  [-3.056, +1.653]  seasons 2023 -0.639, 2024 -0.583
  GUARD mean entry pct -0.03330  one-sided lower -0.06775  (must exceed -0.015)
  simulated line-crossing share -0.01293  [-0.01585, -0.01002]  (secondary)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +40% reads NO DIFFERENCE on 36 slates)

secondaries (slate means):
  C     tickets 299.0  zero-ticket slates 0.319  best>=200 0.167  entry pct 0.53101  worst-decile slate 0.36265  max entry exposure 0.616  simulated crossing 0.11846
  TP0   tickets 277.0  zero-ticket slates 0.292  best>=200 0.125  entry pct 0.49772  worst-decile slate 0.29650  max entry exposure 0.577  simulated crossing 0.10554  entries core/mid/blow 1.000/0.000/0.000
```

**Verdict.**
- **NO DIFFERENCE on tickets (the frozen verdict):** −0.611 per slate [−3.056, +1.653]; tickets 299 → 277.
- **The mean-finish guard, DESCRIPTIVE** (as in Addendum 125), is far below its margin: −0.0333, one-sided lower −0.0678
  against −0.015.
- **The simulated crossing** is lower again: −0.0129 [−0.0159, −0.0100], in-sample, biased against TP0.

**Reading.**
- Removing the game-level contrarian share did NOT fix the thesis. TP0's finish loss (−3.3 points) is close to TP's
  (−4.3, on other banks), and its ticket estimate is smaller but still negative.
- The loss sits in the concentration on the Vegas top-4 totals, not in the contrarian slice. That is consistent with
  study 16's exploratory TP10/TP20 trend, stated as the prior in the preregistration.
- **The thesis portfolio is CLOSED in both forms.** 16b stays tabled, and no further thesis variant is planned.

## Addendum 127 (2026-10-05): study 17 (selection redundancy): DR, EM and PG all NO DIFFERENCE on tickets; de-concentration trades expected tickets for a better distribution

**Setup.**
- **Question.** Redundancy is created at selection: the Week-4 book shared 3.28 players per entry pair, against 1.26
  for random pool rows, and the pool held 122 top-1% rows of which the book took 0. Study 17 re-selects the same K 105
  pool three ways.
- **Arms:**
  - DR (DECISION): diminishing returns, the objective minus λ × prior uses of a player, λ 0.2;
  - EM (DECISION): exposure matching to the entry-share target;
  - PG (DECISION): pool-greedy, s 3;
  - DR35 (λ 0.75) and RND (random rows): EXPLORATORY;
  - all against C, today's plain-mean selection.
- **Preregistration:** `reports/2026-10-05-prereg-study17-selection-redundancy.md`, frozen at `6a616da4` before the
  calibration and any scored bank.
  - Deviation note 1 (`627be501`): settings from the binding outcome-blind calibration census (DR 0.2, DR35 0.75,
    PG 3).
  - Deviation note 2 (`445b7900`): the confirmatory mechanics census, 106/106, 0 errors, committed before the reader
    ran.
- **Panel:** 53 slates (2022–24), banks 1413/1414, the Week-4 plan (22 mean-track contests, 147 entries); B 20,000,
  seed 20261005; two-sided 0.99167 per decision arm (Bonferroni over three).
- **Read and reproduced.** Frozen and read by the reviewer. **Reproduced byte-identically by the laptop:** reader
  `f5c6c493`; raw banks 1413 `e40ae573`, 1414 `5cf0deef`; READ sha `5637364d`. Lab: nfl2
  `production/s17-diminishing-returns-20261005` (results `24279b8`, LEDGER `d06fd69`).

**Reader output (verbatim):**
```
STUDY 17 READER  sha256 f5c6c493395d8cf65a247c8ea19a04463e6a4d40996b73986c577a969253b6e3
DIRECTION: tickets = dealt entries at or above their contest's line (higher = better); pct = share of the sampled field a row BEATS; every difference is ARM - C; POSITIVE favours the arm.
slates 53  banks [1413, 1414]  B 20000  seed 20261005  primary two-sided 0.99167 per decision arm, guard one-sided 0.99167 at -0.015  plan 22 mean-track contests, 147 entries  SETTINGS {"DR": 0.2, "DR35": 0.75, "PG": 3}

== DR vs C  [DECISION]
  PRIMARY tickets per slate -1.623  [-4.057, +0.500]  seasons 2022 -1.824, 2023 -2.139, 2024 -0.917
  GUARD mean entry pct -0.06258  one-sided lower -0.09112  (must exceed -0.015)
  simulated line-crossing share -0.01838  [-0.02056, -0.01633]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +35% reads NO DIFFERENCE on 53 slates)
  vs RND (reference): tickets per slate +3.868  [+1.415, +6.808]  mean entry pct +0.11551  [+0.08297, +0.14801]

== DR35 vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate -2.679  [-5.906, -0.019]  seasons 2022 -3.147, 2023 -3.167, 2024 -1.750
  GUARD mean entry pct -0.10863  one-sided lower -0.14521  (must exceed -0.015)
  simulated line-crossing share -0.03766  [-0.04103, -0.03458]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks

== EM vs C  [DECISION]
  PRIMARY tickets per slate -2.575  [-6.481, +0.660]  seasons 2022 -3.206, 2023 -2.944, 2024 -1.611
  GUARD mean entry pct -0.07752  one-sided lower -0.11762  (must exceed -0.015)
  simulated line-crossing share -0.03426  [-0.03872, -0.03032]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +35% reads NO DIFFERENCE on 53 slates)
  vs RND (reference): tickets per slate +2.915  [+1.286, +4.500]  mean entry pct +0.10057  [+0.07326, +0.12740]

== PG vs C  [DECISION]
  PRIMARY tickets per slate -2.972  [-6.723, +0.198]  seasons 2022 -2.853, 2023 -3.083, 2024 -2.972
  GUARD mean entry pct -0.09022  one-sided lower -0.12702  (must exceed -0.015)
  simulated line-crossing share -0.03783  [-0.04229, -0.03394]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +35% reads NO DIFFERENCE on 53 slates)
  vs RND (reference): tickets per slate +2.519  [+0.896, +4.204]  mean entry pct +0.08786  [+0.06069, +0.11550]

== RND vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate -5.491  [-10.255, -1.522]  seasons 2022 -5.912, 2023 -5.500, 2024 -5.083
  GUARD mean entry pct -0.17809  one-sided lower -0.22995  (must exceed -0.015)
  simulated line-crossing share -0.07627  [-0.08406, -0.06956]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks

secondaries (slate means):
  C     tickets 425.0  zero-ticket slates 0.396  contests with a ticket 0.214  best>=200 0.189  entry pct 0.50732  worst-decile slate 0.28170  simulated crossing 0.12687
        redundancy: top player entry share 0.614, row share 0.495; shared players per entry pair 3.26; QBs 5.3, top QB share 0.456
  DR    tickets 339.0  zero-ticket slates 0.160  contests with a ticket 0.222  best>=200 0.245  entry pct 0.44474  worst-decile slate 0.33533  simulated crossing 0.10849
        redundancy: top player entry share 0.433, row share 0.243; shared players per entry pair 1.44; QBs 15.3, top QB share 0.237
  DR35  tickets 283.0  zero-ticket slates 0.132  contests with a ticket 0.201  best>=200 0.208  entry pct 0.39870  worst-decile slate 0.30943  simulated crossing 0.08921
        redundancy: top player entry share 0.313, row share 0.150; shared players per entry pair 0.92; QBs 20.2, top QB share 0.171
  EM    tickets 288.5  zero-ticket slates 0.104  contests with a ticket 0.208  best>=200 0.236  entry pct 0.42980  worst-decile slate 0.32696  simulated crossing 0.09261
        redundancy: top player entry share 0.330, row share 0.261; shared players per entry pair 1.36; QBs 19.4, top QB share 0.168
  PG    tickets 267.5  zero-ticket slates 0.123  contests with a ticket 0.190  best>=200 0.217  entry pct 0.41710  worst-decile slate 0.28789  simulated crossing 0.08904
        redundancy: top player entry share 0.399, row share 0.277; shared players per entry pair 1.36; QBs 19.6, top QB share 0.203
  RND   tickets 134.0  zero-ticket slates 0.264  contests with a ticket 0.103  best>=200 0.132  entry pct 0.32924  worst-decile slate 0.21447  simulated crossing 0.05060
        redundancy: top player entry share 0.311, row share 0.272; shared players per entry pair 1.09; QBs 22.9, top QB share 0.203
```

**Reading.**
1. **The frozen verdicts are NO DIFFERENCE for DR, EM and PG, and every point estimate is negative.** The mean-finish
   guard, descriptive, fails by a wide margin for all three: the mean finish is 6–9 points lower.
2. **The trade-off is clean and consistent.** De-concentration costs EXPECTED tickets and mean finish (DR −20% of
   tickets) and buys a much better distribution:
   - zero-ticket slates fall from 40% to 10–16%;
   - a 200+ row appears on 22–25% of slates instead of 19%;
   - DR's worst-decile slate improves (0.282 → 0.335).

   DR, the softest arm, costs least. The dose ordering (DR → DR35) shows the cost grows with λ. **It is a
   variance-vs-EV choice for the operator, not a frozen win;** adoption is his.
3. **On this panel C's selection is far better than random** (+5.5 tickets per slate; every arm beats RND). That
   contradicts the 2026 W3–W4 live monkeys, where random beat the live book. Both are stated. Candidate reasons: the
   2026 live projections against the walk-forward replays, the realized-ownership field sampler, and only two live
   weeks.
4. **Study 18's base is therefore λ = 0**, the plain-mean C.

## Addendum 128 (2026-10-05): CORRECTION RECORD for O-32: five analyses re-scored without inactive players; every verdict unchanged

**What was wrong.** Replay panels (`nfl_predictions.slate_player_features`) keep players who did not play, as
`actual` = 0, and have no `was_active` column. Five analyses scored the projection against outcomes at the player
level with those rows included. The reviewer dates the class from the 08-08 salary spine.
- The served/TabPFN calibration family and `served_position_calibration` filter `was_active` and were clean.
- `market_movement_eval` (Addendum 96) predates the spine: 0 non-ACT rows.

**Protocol.** `reports/2026-10-05-o32-correction-protocol.md`, frozen before any re-run, with amendments 1–3:
- ONE shared repair, the game-day `rosters_weekly` ACT join (`analysis/game_day_active.py`), applied identically,
  OFF by default;
- each frozen gate unchanged;
- a local reproduction leg that must match the August Cloud report before the correction is read;
- a whitelist comparison with a leg-identity check;
- for defence PROE, a read of its frozen 2022–25 import only, because the weekly vendor run had appended 2026 runs.

**Results** (original | corrected; every uncorrected leg REPRODUCED the original):

| Study (addendum or report it fed) | Original disposition | Corrected | Non-ACT target rows dropped |
|---|---|---|---|
| FP defence PROE (2026-08-11 protocol) | pass-game tail FAILS | **FAILS** | 8,821 of 21,375 |
| FP QB shell (2026-08-13) | player tail FAILS | **FAILS** | 1,481 of 3,884 |
| market-tail disagreement (2026-08-10) | mechanism gate FAILS | **FAILS** | 7,648 of 18,700 (the prop match had already excluded nearly all) |
| NGS receiver tail (2026-08-10) | gate FAILS | **FAILS** | 535 of 9,059 |
| pass participation (2026-08-10) | SUPPORTS the paid route trial | **SUPPORTS** | 9,989 of 24,205 |

**Reading.**
- No verdict changes. The inactive zeros diluted every comparison, but in none did they hide a signal: in each case
  treatment and control moved together.
- The defence-PROE result that study list item 11 cites stands on clean rows: treatment Brier-30 0.015668 vs control
  0.015666.
- No adopted production lever rested on an in-class measure: `BLEND_W` and `DEFAULT_WIDEN` were fit on played-only
  rows, the TabPFN targets are ownership, and the served family filters.
- **Standing rule:** a player-level projection-vs-outcome measure on replay panels joins game-day ACT (or
  `was_active`) first.
- O-32 is closed. Results: `reports/o32-correction-runs/`.

## Addendum 129 (2026-10-05): study 18 (stacking shapes): WS PASSES (+42% tickets, every season positive, mean finish up); MIX NO DIFFERENCE; the line-aware deal closed

**Setup.**
- **The operator's ask:** "I think we should be doing more like what the winners do … dual stacks", and "not one
  strategy across the entire book".
- **Base:** the plain-mean C (study 17, Addendum 127). No ownership term in any arm; our simulated means.
- **Arms:**
  - MIX (DECISION): a shape portfolio by dealt entries. A1 30% QB+2+ with a bring-back; A2 14% QB+2+ without; B 28%
    QB + exactly 1 + bring-back + a second-game pair, ≤ 3 from the QB's game; C 28% QB + exactly 1, no bring-back, ≤ 3.
  - WS (DECISION): the field-normal shape on every row. QB + ≥ 1, bring-back optional, ≤ 3 from the QB's game, and a
    second-game pair from any game.
  - DS (exploratory): QB + 1 + bring-back + a pair from a top-4-total game.
  - C_LA and MIX_LA (exploratory): line-aware deals.
- **Preregistration:** `reports/2026-10-06-prereg-study18-stack-shapes.md` (`ff205145`), with deviation notes 1
  (`024bbe3f`: the binding census and the §4 path) and 2 (`13575f25`: the confirmatory census, before the reader).
- **Panel:** 53 slates (2022–24), banks 1415/1416. The plan is production's Week-5 draft A (shallow lines p78.8–p90.9),
  repeated 5×: 75 contests, 105 entries. B 20,000, seed 20261005; two-sided 0.9875 per decision arm.
- **Read and reproduced.** Frozen and read by the reviewer. **Reproduced byte-identically by the laptop:** reader
  `1dbef254`; raw banks 1415 `b9cbb0f7`, 1416 `745b151e`; READ sha `9b2649bc`. Lab: nfl2
  `production/s18-stack-shapes-20261005` (results `9c6a6a3`, LEDGER `0738a41`).

**Reader output (verbatim):**
```
STUDY 18 READER  sha256 1dbef2544094a7b6e15ad9487ad33ad92da8536462dfce970e40888ccc8fddda
DIRECTION: tickets = dealt entries at or above their contest's line (higher = better); pct = share of the sampled field a row BEATS; every difference is ARM - its reference (C; for the LA deals, their own book); POSITIVE favours the arm.
slates 53  banks [1415, 1416]  B 20000  seed 20261005  primary two-sided 0.9875 per decision arm, guard one-sided 0.9875 at -0.015  plan 75 mean-track contests, 105 entries  BASE {"lam": 0.0}

== MIX vs C  [DECISION]
  PRIMARY tickets per slate +2.245  [-0.547, +5.349]  seasons 2022 +0.588, 2023 +2.278, 2024 +3.778
  GUARD mean entry pct +0.01097  one-sided lower -0.01249  (must exceed -0.015)
  simulated line-crossing share -0.00536  [-0.00823, -0.00255]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE (a tickets effect smaller than about +38% reads NO DIFFERENCE on 53 slates)

== WS vs C  [DECISION]
  PRIMARY tickets per slate +5.849  [+1.613, +10.481]  seasons 2022 +4.471, 2023 +5.167, 2024 +7.833
  GUARD mean entry pct +0.03251  one-sided lower -0.00027  (must exceed -0.015)
  simulated line-crossing share +0.01061  [+0.00763, +0.01390]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks
  ->  PASS

== DS vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate +2.189  [-0.679, +5.189]  seasons 2022 +2.294, 2023 +1.833, 2024 +2.444
  GUARD mean entry pct +0.02899  one-sided lower +0.00242  (must exceed -0.015)
  simulated line-crossing share -0.00699  [-0.00960, -0.00408]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks

== C_LA vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate -1.198  [-4.038, +2.547]  seasons 2022 -0.029, 2023 -3.972, 2024 +0.472
  GUARD mean entry pct -0.00735  one-sided lower -0.03105  (must exceed -0.015)
  simulated line-crossing share +0.03272  [+0.03039, +0.03515]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks

== MIX_LA vs MIX  [EXPLORATORY (never decision-bearing)]
  PRIMARY tickets per slate +0.085  [-3.566, +4.226]  seasons 2022 +4.147, 2023 -3.861, 2024 +0.194
  GUARD mean entry pct +0.01252  one-sided lower -0.01978  (must exceed -0.015)
  simulated line-crossing share +0.04259  [+0.03880, +0.04679]  (secondary; in-sample)
  dealt identical to C: 0.000 of slate-banks

secondaries (slate means):
  C     tickets 737.0  zero-ticket slates 0.104  contests with a ticket 0.160  best>=200 0.113  entry pct 0.49517  worst-decile slate 0.28121  simulated crossing 0.31701
        shape of dealt entries: qb_plus1 0.000  qb_plus2 1.000  bringback 1.000  dual 0.213  in_qb_game 4.000  games 4.294  rb_with_qb 0.000  rb_bb 0.409  max_entry_share 0.695
  MIX   tickets 856.0  zero-ticket slates 0.151  contests with a ticket 0.186  best>=200 0.179  entry pct 0.50613  worst-decile slate 0.26601  simulated crossing 0.31165
        shape of dealt entries: qb_plus1 0.576  qb_plus2 0.424  bringback 0.493  dual 0.480  in_qb_game 3.032  games 4.764  rb_with_qb 0.114  rb_bb 0.180  max_entry_share 0.575
  WS    tickets 1047.0  zero-ticket slates 0.151  contests with a ticket 0.216  best>=200 0.189  entry pct 0.52768  worst-decile slate 0.21621  simulated crossing 0.32762
        shape of dealt entries: qb_plus1 0.921  qb_plus2 0.079  bringback 0.129  dual 1.000  in_qb_game 2.360  games 4.829  rb_with_qb 0.152  rb_bb 0.051  max_entry_share 0.694
  DS    tickets 853.0  zero-ticket slates 0.094  contests with a ticket 0.184  best>=200 0.123  entry pct 0.52416  worst-decile slate 0.33710  simulated crossing 0.31001
        shape of dealt entries: qb_plus1 1.000  qb_plus2 0.000  bringback 1.000  dual 1.000  in_qb_game 3.000  games 4.375  rb_with_qb 0.000  rb_bb 0.347  max_entry_share 0.692
  C_LA  tickets 673.5  zero-ticket slates 0.434  contests with a ticket 0.139  best>=200 0.057  entry pct 0.48781  worst-decile slate 0.24998  simulated crossing 0.34972
        shape of dealt entries: qb_plus1 0.000  qb_plus2 1.000  bringback 1.000  dual 0.199  in_qb_game 4.000  games 4.176  rb_with_qb 0.000  rb_bb 0.424  max_entry_share 0.974
  MIX_LA tickets 860.5  zero-ticket slates 0.377  contests with a ticket 0.175  best>=200 0.057  entry pct 0.51865  worst-decile slate 0.23753  simulated crossing 0.35424
        shape of dealt entries: qb_plus1 0.461  qb_plus2 0.539  bringback 0.863  dual 0.456  in_qb_game 3.458  games 4.312  rb_with_qb 0.056  rb_bb 0.340  max_entry_share 0.963
```

**Reading.**
1. **WS PASSES the frozen rule.** Tickets rise from 737 to 1,047 (+42%), every season is positive, and the mean finish
   is up 3.3 points.
   - In practice WS is QB + 1 (92%), a second-game pair (100%), ≤ 3 from the QB's game, rarely a bring-back (13%), 4.8
     games.
   - Its cost is a wider spread: the worst-decile slate falls from 0.281 to 0.216, and zero-ticket slates rise from
     10% to 15%.
2. **MIX is NO DIFFERENCE.** Its point estimate is positive and its guard holds, but it is not significant.
   - DS reaches about half WS's gain with the best tail.
   - The common factor in the gainers is the second-game pair with ≤ 3 from the QB's game; the bring-back looks costly
     at these lines.
3. **The result is plan-specific.** It was measured at draft A's shallow lines (p79–p91), with tickets counted per entry.
4. **Transfer caveat.** There is no ownership term in any arm, and the projections are ours. "WS + FP term + FP
   projections" is a composite, untested as such; there is no FP history for 2022–24.
5. **The line-aware deal is CLOSED:** no gain, and it concentrates the top player in 96–97% of entries.

**What it can do** (§6). The PASS is a reason to offer a reversible Week-5 trial of WS, built through production's
`--main mix` machinery as a whole-book portfolio (`--mix-portfolio ws`, the laptop's build). The operator decides.

## Addendum 130 (2026-10-05): study 24 (an all-distinct deal and a per-game QB cap, on the operator's real Week-5 plan): both NO DIFFERENCE; the cap fails his tolerance and is not offered

**Setup.**
- **The operator's goal, the first study built on it:** "If i could win one 333, 555 or 4444 or $500 in the milly, the
  week is a success". Big = "any one except a $20 milly ticket". His tolerance: "accepting 20% fewer" expected big
  seats. His dealing choice: "All distinct".
- **Primary:** P(≥ 1 big seat) per slate. It is computed exactly per contest from each dealt entry's realized
  percentile in the sampled field: P(Bin(N − m, 1 − F_best) ≤ S − 1), combined over big contests.
- **Guards:** guard 1 is the mean entry finish (one-sided 0.975 at −0.015). Guard 2 is the operator's tolerance:
  expected big seats ratio ≥ 0.80.
- **Plan:** his revised Week-5 entries (Rev1: 19 contests, 24 entries, 23 in 18 big contests; the Milly judged at its
  $500+ line).
- **Arms:** each is read against its reference, on study 18's WS shape, under production's main caps for its own K
  (deviation note 1, the laptop's objection: player int(0.5 × K), DST int(0.25 × K); head K 20, sequential/distinct K
  24).
  - SEQD (DECISION vs WS): every entry its own lineup, with overlap replacements drawn from spare rows.
  - G25S (DECISION vs SEQD): every game's QBs in ≤ 6 of the 24 entries, dealt all-distinct; spares count against the
    budget (deviation note 2).
  - Exploratory: G25 (the cap with the head deal), SEQ (production's existing sequential deal) and G1 (the #1-total
    game's QBs only, the first draft's arm; the smoke showed WS concentrating on games OTHER than the #1 total).
- **Preregistration:** `reports/2026-10-06-prereg-study24-qb-game-cap.md` (frozen `4cadd426`), with census notes 1–2
  and deviation notes 1–2, all before any scored bank. The binding census v3 passed every §2a check and the laptop
  acked it.
- **Panel:** 53 slates (2022–24), banks 1417/1418; B 20,000, seed 20261006.
- **Read and reproduced.** Frozen and read by the reviewer. **Reproduced byte-identically by the laptop:** reader
  `e1a4968a`; raw 1417 `996e7f43`, 1418 `92306276`; READ `b9733686`. Lab: nfl2 `production/s24-qb-game-cap-20261006`
  (READ `9ed3925`; confirmatory census `b29ca1f`, committed before the read).

**Reader output (verbatim):**
```
STUDY 24 READER  sha256 e1a4968ae3eea7a8a382b53d98ee01392016f5c6af5ece5a00f99d591dfdd933
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (SEQD, G25, SEQ, G1: WS; G25S: SEQD); POSITIVE favours the arm.
slates 53  banks [1417, 1418]  B 20000  seed 20261006  primary two-sided 0.975 per decision arm, guard 1 one-sided 0.975 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 19 mean-track contests, 24 entries (23 in 18 big contests)  QB-game cap [6] entries  BASE {"lam": 0.0}

== SEQD vs WS  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.01155  [-0.02889, +0.05200]  seasons 2022 +0.00131, 2023 -0.00720, 2024 +0.03998
  GUARD 1 mean entry pct -0.01558  one-sided lower -0.02635  (must exceed -0.015)
  GUARD 2 expected big seats 0.51220 vs WS 0.53795  ratio 0.952  (must be >= 0.80)
  dealt identical to WS: 0.000 of slate-banks
  ->  NO DIFFERENCE

== G25S vs SEQD  [DECISION]
  PRIMARY P(>= 1 big seat) per slate -0.01828  [-0.07633, +0.03442]  seasons 2022 -0.01104, 2023 +0.02540, 2024 -0.06878
  GUARD 1 mean entry pct +0.00280  one-sided lower -0.01071  (must exceed -0.015)
  GUARD 2 expected big seats 0.39907 vs SEQD 0.51220  ratio 0.779  (must be >= 0.80)
  dealt identical to SEQD: 0.000 of slate-banks
  ->  NO DIFFERENCE

== G25 vs WS  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate -0.01776  [-0.08059, +0.03743]  seasons 2022 -0.03161, 2023 +0.00819, 2024 -0.03064
  GUARD 1 mean entry pct -0.00082  one-sided lower -0.01408  (must exceed -0.015)
  GUARD 2 expected big seats 0.41601 vs WS 0.53795  ratio 0.773  (must be >= 0.80)
  dealt identical to WS: 0.000 of slate-banks

== SEQ vs WS  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.03044  [-0.01443, +0.07743]  seasons 2022 +0.01530, 2023 +0.01127, 2024 +0.06391
  GUARD 1 mean entry pct -0.00795  one-sided lower -0.01631  (must exceed -0.015)
  GUARD 2 expected big seats 0.56133 vs WS 0.53795  ratio 1.043  (must be >= 0.80)
  dealt identical to WS: 0.000 of slate-banks

== G1 vs WS  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.00581  [-0.01777, +0.03482]  seasons 2022 -0.00863, 2023 -0.01391, 2024 +0.03916
  GUARD 1 mean entry pct +0.00394  one-sided lower -0.00341  (must exceed -0.015)
  GUARD 2 expected big seats 0.48187 vs WS 0.53795  ratio 0.896  (must be >= 0.80)
  dealt identical to WS: 0.302 of slate-banks

secondaries (slate means):
  WS  P(>=1 big) 0.25666  expected big seats 0.53795  P(>=2 contests) 0.13613  slates P(>=1 big) < 1% 0.509  tickets 44.5  best>=200 0.094  entry pct 0.50138  worst-decile slate 0.26092  simulated P(>=1 big) 0.48915
      shape of dealt entries: qb_game1_share 0.253  qb_game_top4_share 0.708  qb_games 3.415  qb_game_max_share 0.535  qb_plus1 0.937  bringback 0.154  dual 1.000  in_qb_game 2.386  games 4.858  max_entry_share 0.584
  SEQD P(>=1 big) 0.26821  expected big seats 0.51220  P(>=2 contests) 0.11856  slates P(>=1 big) < 1% 0.443  tickets 45.5  best>=200 0.085  entry pct 0.48580  worst-decile slate 0.25690  simulated P(>=1 big) 0.50562
      shape of dealt entries: qb_game1_share 0.260  qb_game_top4_share 0.702  qb_games 3.717  qb_game_max_share 0.472  qb_plus1 0.941  bringback 0.168  dual 1.000  in_qb_game 2.393  games 4.892  max_entry_share 0.485
  G25S P(>=1 big) 0.24994  expected big seats 0.39907  P(>=2 contests) 0.09412  slates P(>=1 big) < 1% 0.387  tickets 38.0  best>=200 0.066  entry pct 0.48860  worst-decile slate 0.23065  simulated P(>=1 big) 0.51670
      shape of dealt entries: qb_game1_share 0.182  qb_game_top4_share 0.586  qb_games 5.660  qb_game_max_share 0.246  qb_plus1 0.958  bringback 0.134  dual 1.000  in_qb_game 2.336  games 4.902  max_entry_share 0.483
  G25 P(>=1 big) 0.23890  expected big seats 0.41601  P(>=2 contests) 0.11017  slates P(>=1 big) < 1% 0.425  tickets 36.0  best>=200 0.057  entry pct 0.50055  worst-decile slate 0.23975  simulated P(>=1 big) 0.50103
      shape of dealt entries: qb_game1_share 0.186  qb_game_top4_share 0.596  qb_games 5.208  qb_game_max_share 0.276  qb_plus1 0.954  bringback 0.127  dual 1.000  in_qb_game 2.333  games 4.867  max_entry_share 0.585
  SEQ P(>=1 big) 0.28710  expected big seats 0.56133  P(>=2 contests) 0.13450  slates P(>=1 big) < 1% 0.453  tickets 49.0  best>=200 0.085  entry pct 0.49342  worst-decile slate 0.25629  simulated P(>=1 big) 0.49676
      shape of dealt entries: qb_game1_share 0.257  qb_game_top4_share 0.703  qb_games 3.472  qb_game_max_share 0.496  qb_plus1 0.939  bringback 0.161  dual 1.000  in_qb_game 2.390  games 4.880  max_entry_share 0.540
  G1  P(>=1 big) 0.26247  expected big seats 0.48187  P(>=2 contests) 0.13441  slates P(>=1 big) < 1% 0.472  tickets 43.5  best>=200 0.057  entry pct 0.50532  worst-decile slate 0.26092  simulated P(>=1 big) 0.49161
      shape of dealt entries: qb_game1_share 0.148  qb_game_top4_share 0.655  qb_games 3.868  qb_game_max_share 0.513  qb_plus1 0.937  bringback 0.144  dual 1.000  in_qb_game 2.366  games 4.857  max_entry_share 0.584
```

**Reading.**
1. **The cap (G25S) is NO DIFFERENCE, with the point estimate negative (−1.8 points of P(≥ 1 big seat)).** It fails
   the operator's tolerance: expected big seats fall 22% (ratio 0.779 < 0.80).
   - It is variance shaping, as study 1's game budget was (Addendum 122): fewer near-dead slates (P < 1% on 0.39 of
     slates vs 0.44) but a lower ceiling (best ≥ 200: 0.066 vs 0.085).
   - Finishing first needs lineups that can spike, and spreading the QBs across games trades that away. **Not
     offered; no production port.**
2. **The all-distinct deal (SEQD) is NO DIFFERENCE (+1.2 points)** and costs mean finish: guard 1's lower bound is
   −0.026, past the margin; descriptive, since the primary did not pass.
   - The mechanism: the replacements it draws are weaker spare rows. Production's existing sequential deal (SEQ,
     exploratory), which REUSES a strong row across contests instead, beats SEQD on every big-seat number (P 0.287 vs
     0.268; expected seats 0.561 vs 0.512).
   - **No port.** SEQ is a risk preference at most: the best point estimate (+3.0 points), expected seats kept (1.04),
     a small mean-finish cost (lower bound −0.016), and no code needed.
3. **Concentration is real but is not what limits his chance.** WS dealt an average of 12.8 of 24 entries to one
   game's QBs (maximum 24), against 5.9 under the cap, and the cap did not help.
4. **The absolute numbers are optimistic.** P(≥ 1 big seat) per week is about 0.26–0.29 on practice slates with
   modelled, softer Milly-style fields; real satellite fields are sharper. Half the slates sit below 1%. The in-sample
   simulation says about 0.50, so the simulations' absolute big-seat numbers are not to be trusted.
5. **Transfer:** our projections, no ownership term, production's caps. "WS + FP + term" is untested as a composite.

**What it can do** (§6): nothing passed. For Week 5 the operator chooses between today's head deal (the default,
`ENTER_LAYOUT=head`) and production's sequential deal (no code) as a risk preference, with this read stated. The cap
and the all-distinct port are not offered.

## Addendum 131 (2026-10-06): study 18b (WS vs the house shape on the operator's goal, his real Week-5 plan, production's caps): NO DIFFERENCE; the shape is a wash on his plan

**Setup.**
- **Why:** Friday's shape recommendation (WS) rested on study 18 (Addendum 129). That study measured tickets, at draft
  A's shallow lines, under the lab's loose caps. This study asks the shape question on the operator's terms.
- **Plan:** his Rev1 Week-5 plan (19 contests, 24 entries, 23 in 18 big contests).
- **Caps:** production's main caps per layout (head 10/5, sequential 12/6).
- **Primary:** P(≥ 1 big seat) per slate, computed exactly per contest against modelled Milly-style fields.
- **Guards:** mean finish (−0.015) and his tolerance (expected big seats ≥ 0.80).
- **Arms:**
  - C: PRODUCTION_STACK by identity, head layout; the reference.
  - WS (DECISION vs C): head layout.
  - CQ and WSQ (exploratory): production's sequential deal.
- **Preregistration:** `reports/2026-10-06-prereg-study18b-ws-vs-house.md` (frozen `43e944f6`, after the operator's
  "proceed with testing unless there is a valid reason for waiting").
- **Panel:** 53 slates (2022–24), banks 1419/1420; B 20,000, seed 20261007; two-sided 0.95. The binding census
  (1406, 53/53) was clean and acked by the laptop.
- **Read and reproduced.** Frozen and read by the reviewer. **Reproduced byte-identically by the laptop:** reader
  `5fb03df3`; raw 1419 `1d8d6c10`, 1420 `ecdd665b`; READ `5b4c7eec`. Lab: nfl2 `production/s18b-ws-vs-house-20261006`
  (READ `0113ecb`, LEDGER `6196f8c`).

**Reader output (verbatim):**
```
STUDY 18B READER  sha256 5fb03df3f57124afc0d955bdd18321b669447ed75cb5705f5bbb19067e0d9bc0
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (WS, CQ: C; WSQ: CQ); POSITIVE favours the arm.
slates 53  banks [1419, 1420]  B 20000  seed 20261007  primary two-sided 0.95 (one decision arm), guard 1 one-sided 0.95 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 19 mean-track contests, 24 entries (23 in 18 big contests)  production row caps ['{"C": [10, 5], "CQ": [12, 6], "WS": [10, 5], "WSQ": [12, 6]}']  BASE {"lam": 0.0}

== WS vs C  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.00634  [-0.07013, +0.08232]  seasons 2022 +0.07465, 2023 -0.12161, 2024 +0.06977
  GUARD 1 mean entry pct +0.01347  one-sided lower -0.00248  (must exceed -0.015)
  GUARD 2 expected big seats 0.49848 vs C 0.51633  ratio 0.965  (must be >= 0.80)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE

== CQ vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.00747  [-0.02895, +0.04273]  seasons 2022 +0.03423, 2023 -0.04994, 2024 +0.03960
  GUARD 1 mean entry pct -0.00240  one-sided lower -0.00879  (must exceed -0.015)
  GUARD 2 expected big seats 0.48433 vs C 0.51633  ratio 0.938  (must be >= 0.80)
  dealt identical to C: 0.000 of slate-banks

== WSQ vs CQ  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.01844  [-0.05256, +0.09098]  seasons 2022 +0.01256, 2023 -0.03019, 2024 +0.07262
  GUARD 1 mean entry pct +0.00556  one-sided lower -0.00877  (must exceed -0.015)
  GUARD 2 expected big seats 0.46698 vs CQ 0.48433  ratio 0.964  (must be >= 0.80)
  dealt identical to CQ: 0.000 of slate-banks

secondaries (slate means):
  C   P(>=1 big) 0.25582  expected big seats 0.51633  P(>=2 contests) 0.13110  slates P(>=1 big) < 1% 0.481  tickets 45.5  best>=200 0.094  entry pct 0.49876  worst-decile slate 0.27077  simulated P(>=1 big) 0.50905
      shape of dealt entries: qb_game1_share 0.242  qb_game_top4_share 0.750  qb_games 3.396  qb_game_max_share 0.540  qb_plus1 0.000  bringback 1.000  dual 0.219  in_qb_game 4.000  games 4.297  max_entry_share 0.586
  WS  P(>=1 big) 0.26216  expected big seats 0.49848  P(>=2 contests) 0.11764  slates P(>=1 big) < 1% 0.358  tickets 43.0  best>=200 0.075  entry pct 0.51223  worst-decile slate 0.20319  simulated P(>=1 big) 0.49135
      shape of dealt entries: qb_game1_share 0.242  qb_game_top4_share 0.688  qb_games 3.349  qb_game_max_share 0.524  qb_plus1 0.923  bringback 0.146  dual 1.000  in_qb_game 2.386  games 4.854  max_entry_share 0.584
  CQ  P(>=1 big) 0.26329  expected big seats 0.48433  P(>=2 contests) 0.12124  slates P(>=1 big) < 1% 0.472  tickets 41.5  best>=200 0.075  entry pct 0.49636  worst-decile slate 0.25067  simulated P(>=1 big) 0.51680
      shape of dealt entries: qb_game1_share 0.246  qb_game_top4_share 0.734  qb_games 3.500  qb_game_max_share 0.500  qb_plus1 0.000  bringback 1.000  dual 0.213  in_qb_game 4.000  games 4.310  max_entry_share 0.535
  WSQ P(>=1 big) 0.28173  expected big seats 0.46698  P(>=2 contests) 0.10984  slates P(>=1 big) < 1% 0.396  tickets 41.0  best>=200 0.085  entry pct 0.50193  worst-decile slate 0.19881  simulated P(>=1 big) 0.49692
      shape of dealt entries: qb_game1_share 0.254  qb_game_top4_share 0.695  qb_games 3.368  qb_game_max_share 0.498  qb_plus1 0.933  bringback 0.147  dual 1.000  in_qb_game 2.367  games 4.881  max_entry_share 0.536
```

**Reading.**
1. **On his goal and plan the shape is a wash.**
   - WS vs C: +0.6 points of P(≥ 1 big seat), interval −7.0 to +8.2, with seasons +7.5 / −12.2 / +7.0.
   - Both guards hold.
2. **The trade-offs** (secondaries, C → WS):
   - WS gives a better mean entry finish (0.499 → 0.512) and fewer near-dead slates (P < 1%: 0.48 → 0.36).
   - The house shape gives a slightly higher ceiling (best ≥ 200: 0.094 vs 0.075) and a better worst decile (0.271 vs
     0.203).
3. **Study 18's +42% tickets does not carry to his plan.** Its edge was at shallow lines (p79–p91). His satellites need
   first place (p95.7–p99.94), where the house shape's correlation keeps pace.
4. **Studies 24 and 18b together:**
   - neither the shape, the per-game cap nor the all-distinct deal moves his chance of a big win measurably on the
     2022–24 practice slates;
   - the absolute chance is about one week in four, with easier fields than real satellites, so lower in practice.
5. **Transfer:** our projections, no ownership term, no FP (no FP history exists for 2022–24).

**What it can do** (§5): WS is a preference, not a tested gain on his goal. Doing nothing keeps today's house shape.
WS is now safe to run (the late-scratch fix `ddd470ed`), so the operator chooses on Friday.

## Addendum 132 (2026-10-06): study 26 (a one-game SHOOTOUT build vs the house shape, on the operator's goal and FINAL plan): NO DIFFERENCE, with the first consistent ceiling signal; player-upside (p90) negative again

**Setup.**
- **The operator's ask:** "around the clock efforts to try different strategies of selecting boom players, sorting,
  testing usage of route share data etc".
- **What the ledger sweep found closed at deep lines:** player-upside objectives (p90 Add. 2; q97 / q98.75
  PREREG-006/010; the finish objective PREREG-098; simulated P(≥ line) L14) and sorting by simulated tail (Add. 62/65,
  09-22). Building MORE correlation was untested there; L10's CAP5 was read only at p89.
- **Plan:** his FINAL Rev2 Week-5 plan. 29 contests, 53 entries; his Milly super-satellites and the $125 FFWC are
  PINNED to rows 1–5 by his rule; 26 entries in 21 big contests.
- **Caps:** production's caps 11 / 5 (head K 22).
- **Arms:**
  - C (PRODUCTION_STACK, MPG 4): the reference;
  - SH (DECISION): QB + ≥ 3 WR/TE + a bring-back, MPG 5, i.e. five from one game, as the whole book;
  - C5 (exploratory): the house rules at MPG 5;
  - P90 (exploratory): the house shape on each player's simulated p90.
- **Preregistration:** `reports/2026-10-06-prereg-study26-shootout.md` (frozen `36182d74`).
  - It discloses, before the freeze, that a smoke's grep printed one throwaway slate's secondaries (2023 W9); the design
    was unchanged.
  - **Deviation note 1** (`e0ea2991`, after the scored run started, before any read): the operator rules out a
    whole-book shootout ("I would only want to use it a very small percentage. We know that milly winners use fewer
    players than that"). The read answers only whether the shape helps or hurts.
- **Panel:** 53 slates (2022–24), banks 1421/1422; B 20,000, seed 20261008; two-sided 0.95.
- **Read and reproduced.** Frozen and read by the reviewer. **Reproduced byte-identically by the laptop**, the reader and
  the agreed non-decision sensitivity: reader `86b3abb2`; READ `d343a218`; SENS `261f348a`. Lab: nfl2
  `production/s26-boom-objective-20261006`.

**Reader output (verbatim):**
```
STUDY 26 READER  sha256 86b3abb2c59a6ac5c88a894541af6e82e6174b445d43bad08b18d54a0c57e8c8
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (C); POSITIVE favours the arm.
slates 53  banks [1421, 1422]  B 20000  seed 20261008  primary two-sided 0.95 (one decision arm), guard 1 one-sided 0.95 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 29 mean-track contests, 53 entries (26 in 21 big contests)  production row caps ['{"all": [11, 5]}']  BASE {"lam": 0.0}

== SH vs C  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.02378  [-0.02827, +0.07484]  seasons 2022 +0.06677, 2023 +0.03087, 2024 -0.02390
  GUARD 1 mean entry pct -0.01450  one-sided lower -0.03685  (must exceed -0.015)
  GUARD 2 expected big seats 0.70493 vs C 0.61098  ratio 1.154  (must be >= 0.80)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE

== C5 vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.00498  [-0.02430, +0.03599]  seasons 2022 +0.04260, 2023 +0.01772, 2024 -0.04330
  GUARD 1 mean entry pct +0.00263  one-sided lower -0.00789  (must exceed -0.015)
  GUARD 2 expected big seats 0.60877 vs C 0.61098  ratio 0.996  (must be >= 0.80)
  dealt identical to C: 0.047 of slate-banks

== P90 vs C  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate -0.02741  [-0.09218, +0.04176]  seasons 2022 -0.02766, 2023 -0.04154, 2024 -0.01305
  GUARD 1 mean entry pct -0.01290  one-sided lower -0.03749  (must exceed -0.015)
  GUARD 2 expected big seats 0.50086 vs C 0.61098  ratio 0.820  (must be >= 0.80)
  dealt identical to C: 0.000 of slate-banks

secondaries (slate means):
  C   P(>=1 big) 0.26642  expected big seats 0.61098  P(>=2 contests) 0.15903  slates P(>=1 big) < 1% 0.472  tickets 124.0  best>=200 0.075  entry pct 0.50644  worst-decile slate 0.25689  simulated P(>=1 big) 0.51142
      shape of dealt entries: five_from_one_game 0.000  qb_plus3 0.000  qb_game1_share 0.252  qb_game_top4_share 0.776  qb_games 3.321  qb_game_max_share 0.705  qb_plus1 0.000  bringback 1.000  dual 0.221  in_qb_game 4.000  games 4.281  max_entry_share 0.788
  SH  P(>=1 big) 0.29020  expected big seats 0.70493  P(>=2 contests) 0.13285  slates P(>=1 big) < 1% 0.368  tickets 168.0  best>=200 0.104  entry pct 0.49194  worst-decile slate 0.28535  simulated P(>=1 big) 0.51422
      shape of dealt entries: five_from_one_game 1.000  qb_plus3 1.000  qb_game1_share 0.246  qb_game_top4_share 0.753  qb_games 3.245  qb_game_max_share 0.709  qb_plus1 0.000  bringback 1.000  dual 0.135  in_qb_game 5.000  games 3.621  max_entry_share 0.780
  C5  P(>=1 big) 0.27139  expected big seats 0.60877  P(>=2 contests) 0.15311  slates P(>=1 big) < 1% 0.453  tickets 142.0  best>=200 0.085  entry pct 0.50907  worst-decile slate 0.26290  simulated P(>=1 big) 0.51728
      shape of dealt entries: five_from_one_game 0.295  qb_plus3 0.025  qb_game1_share 0.253  qb_game_top4_share 0.767  qb_games 3.387  qb_game_max_share 0.704  qb_plus1 0.000  bringback 1.000  dual 0.190  in_qb_game 4.295  games 4.114  max_entry_share 0.789
  P90 P(>=1 big) 0.23901  expected big seats 0.50086  P(>=2 contests) 0.12725  slates P(>=1 big) < 1% 0.453  tickets 104.0  best>=200 0.066  entry pct 0.49353  worst-decile slate 0.23094  simulated P(>=1 big) 0.50112
      shape of dealt entries: five_from_one_game 0.000  qb_plus3 0.000  qb_game1_share 0.238  qb_game_top4_share 0.749  qb_games 3.311  qb_game_max_share 0.706  qb_plus1 0.000  bringback 1.000  dual 0.213  in_qb_game 4.000  games 4.217  max_entry_share 0.790
```

**The agreed NON-DECISION sensitivity (verbatim; the disclosed slate excluded):**
```
STUDY 26 SENSITIVITY (NON-DECISION; the frozen reader's verdict governs)  reader sha256 86b3abb2c59a6ac5c88a894541af6e82e6174b445d43bad08b18d54a0c57e8c8  this script sha256 13ddd5df31fe645080423f40c441b1b8d94299014fe91ba353ce0fe2a4b26822
  SH vs C WITHOUT 2023 W9 (52 slates): P(>= 1 big seat) +0.02404  [-0.02951, +0.07686]  seasons 2022 +0.06677, 2023 +0.03208, 2024 -0.02390
  C5 vs C WITHOUT 2023 W9 (52 slates): P(>= 1 big seat) +0.00507  [-0.02447, +0.03721]  seasons 2022 +0.04260, 2023 +0.01876, 2024 -0.04330
  P90 vs C WITHOUT 2023 W9 (52 slates): P(>= 1 big seat) -0.02653  [-0.09222, +0.04359]  seasons 2022 -0.02766, 2023 -0.03968, 2024 -0.01305
```

**Reading.**
1. **The shootout is NO DIFFERENCE on P(≥ 1 big seat)** (+2.4 points, interval −2.8 to +7.5; seasons +6.7 / +3.1 /
   −2.4). The sensitivity without the disclosed slate is the same (+2.4).
2. **But it is the first lever with a consistent CEILING signal on his goal** (C → SH):
   - expected big seats +15% (0.611 → 0.705);
   - tickets 124 → 168;
   - weeks with a 200+ lineup 7.5% → 10.4%;
   - near-dead weeks 47% → 37%;
   - a better worst decile.

   The cost is about 1.4 points of mean finish, which is what a ceiling build should cost.
3. **Whole-book use is off the table by the operator's choice.** A small sleeve needs its own study (study 27). Under his
   pins a top rank is many entries (rank 1 = 10 entries), so a small share by entries sits on the single-entry ranks
   6–22.
4. **Player upside (P90) is negative again** (−2.7 points; expected seats 0.82×), consistent with every prior read.
   **Allowing five (C5) is flat:** the plain mean rarely takes the fifth player.
5. **Transfer:** our projections, no ownership term, no FP.

## Addendum 133 (2026-10-06): study 28 (the WINNERS' SHAPE MIX vs the house shape, on the operator's goal and final plan): NO DIFFERENCE, every season positive, both guards intact — the closest result of the week

**Setup.**
- **The operator's ask:** "I like what we discussed previously of mirroring how the winners play - with a mix of
  stacks, double stacks, etc.  Is there a reason that we aren't trying to play the way the winners play?" Study 18 had
  read MIX only at shallow lines with the lab's loose caps.
- **The MIX cells** (study 18's, by DEALT ENTRIES):
  - A1 30%: QB + 2+, a bring-back;
  - A2 14%: QB + 2+, no bring-back;
  - B 28%: QB + 1, a bring-back, a second-game pair, ≤ 3 from the QB's game;
  - C 28%: QB + 1, no bring-back, ≤ 3.
- **The build** is production's `mix_rows`: K = 22 rows by quota, the cells largest first through one shared state, and
  the entry-weighted interleave with PIN-AWARE weights [10, 8, 7, 6, 5, 1 × 17].
- **Plan and caps:** his Rev2 plan with pins; production caps 11 / 5; head; P(≥ 1 big seat).
- **Arms:** MIX (DECISION) vs C (`PRODUCTION_STACK`). MIXNP (production's pin-stripping weights, O-35) is exploratory
  vs MIX.
- **Preregistration:** `reports/2026-10-06-prereg-study28-winners-mix.md` (frozen `9bb2d42b`). A smoke caught a
  meta-key bug before the freeze (fixed `669f92b`).
- **Census:** the binding census (1406, 53/53) dealt A1 .302 / A2 .149 / B .240 / C .308, with 0 passes.
- **Panel:** 53 slates, banks 1425/1426; B 20,000, seed 20261010; two-sided 0.95.
- **Read and reproduced.** Read by the reviewer; **reproduced byte-identically by the laptop** (reader `d320a368`;
  READ `5366c535`). Lab: nfl2 `production/s28-winners-mix-20261006`.

**Reader output (verbatim):**
```
STUDY 28 READER  sha256 d320a3689d108b07b2f723977896512c9fa50ab1a1ae26f9288b72d758442f4e
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (MIX: C; MIXNP: MIX); POSITIVE favours the arm.
slates 53  banks [1425, 1426]  B 20000  seed 20261010  primary two-sided 0.95 (one decision arm), guard 1 one-sided 0.95 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 29 mean-track contests, 53 entries (26 in 21 big contests)  production row caps ['{"all": [11, 5]}']  BASE {"lam": 0.0}

== MIX vs C  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.06081  [-0.01184, +0.13846]  seasons 2022 +0.02925, 2023 +0.05435, 2024 +0.09708
  GUARD 1 mean entry pct +0.01259  one-sided lower -0.00539  (must exceed -0.015)
  GUARD 2 expected big seats 0.55447 vs C 0.49527  ratio 1.120  (must be >= 0.80)
  dealt identical to C: 0.000 of slate-banks
  ->  NO DIFFERENCE

== MIXNP vs MIX  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate +0.00491  [-0.02392, +0.03414]  seasons 2022 +0.01459, 2023 +0.00793, 2024 -0.00724
  GUARD 1 mean entry pct -0.00056  one-sided lower -0.00171  (must exceed -0.015)
  GUARD 2 expected big seats 0.53217 vs MIX 0.55447  ratio 0.960  (must be >= 0.80)
  dealt identical to MIX: 0.000 of slate-banks

secondaries (slate means):
  C   P(>=1 big) 0.23564  expected big seats 0.49527  P(>=2 contests) 0.12332  slates P(>=1 big) < 1% 0.481  tickets 119.5  best>=200 0.075  entry pct 0.50142  worst-decile slate 0.24260  simulated P(>=1 big) 0.51239
      shape of dealt entries: qb_game1_share 0.235  qb_game_top4_share 0.758  qb_games 3.330  qb_game_max_share 0.700  qb_plus1 0.000  bringback 1.000  dual 0.220  in_qb_game 4.000  games 4.263  max_entry_share 0.788
  MIX P(>=1 big) 0.29645  expected big seats 0.55447  P(>=2 contests) 0.13826  slates P(>=1 big) < 1% 0.415  tickets 164.5  best>=200 0.075  entry pct 0.51401  worst-decile slate 0.29023  simulated P(>=1 big) 0.51475
      shape of dealt entries: qb_game1_share 0.244  qb_game_top4_share 0.730  qb_games 3.736  qb_game_max_share 0.513  qb_plus1 0.549  bringback 0.543  dual 0.481  in_qb_game 3.107  games 4.680  max_entry_share 0.666
  MIXNP P(>=1 big) 0.30137  expected big seats 0.53217  P(>=2 contests) 0.13699  slates P(>=1 big) < 1% 0.396  tickets 161.5  best>=200 0.075  entry pct 0.51345  worst-decile slate 0.28999  simulated P(>=1 big) 0.52407
      shape of dealt entries: qb_game1_share 0.244  qb_game_top4_share 0.730  qb_games 3.736  qb_game_max_share 0.512  qb_plus1 0.557  bringback 0.537  dual 0.480  in_qb_game 3.094  games 4.685  max_entry_share 0.667
```

**Reading.**
1. **MIX vs C is NO DIFFERENCE, but the closest result of the week on his goal.**
   - P(≥ 1 big seat) +6.1 points (interval −1.2 to +13.8), positive in EVERY season (+2.9 / +5.4 / +9.7).
   - Both guards hold: mean finish +1.3 points; expected big seats ×1.12.
2. **It improves his goal measures and the downside together** (C → MIX):
   - P(≥ 1 big) .236 → .296;
   - expected big seats .495 → .554;
   - P(≥ 2 contests) .123 → .138;
   - tickets 119.5 → 164.5;
   - mean finish .501 → .514;
   - the worst decile .243 → .290;
   - near-dead weeks .48 → .42.

   The best ≥ 200 share is unchanged (.075). The dealt shape (QB+1 .55, bring-back .54, dual .48) sits near the 2026
   top-1% rates, and the top player's entry share falls from .79 to .67.
3. **By §5 (frozen):** "NO DIFFERENCE with both guards intact: a legitimate reason to choose MIX as his stated
   preference ('mirroring how the winners play'), said plainly as a preference, not a tested gain."
   - **Arming:** `--main mix --mix-portfolio mix`, with O-35 (`ce7ba02b`) merged first and the MIX Sunday spares
     (`ddd470ed`).
   - **O-35's own effect is small here** (MIXNP vs MIX +0.5 points). The fix is kept for correctness.
4. **Transfer:** our projections; no ownership term; no FP.

## Addendum 134 (2026-10-06): study 29 (the live ownership term on the winners' mix, at first-place-only lines): NO DIFFERENCE at the frozen rule, both seasons negative, −29% expected big seats — recommended OFF for Week 5

**Setup.**
- **The term:** the live main adds tilt × predicted ownership % to the objective (skill players only;
  `union_reselect.own_bonus`). Week 5 would arm FP's projection at 0.20, with LAG 0.10 as the fallback (LineStar
  retired).
- **The prior:** L24 had the term neutral at shallow lines and −14% tickets at p99.
- **Arms** (on study 28's MIX: production `mix_rows`, pin-aware weights, caps 11 / 5, head, his Rev2 pins):
  - MIX: no term; the reference;
  - MIXT (DECISION): + 0.20 × TABPFN_LS (L24's stage-1 walk-forward predictions, sha `5c8384d6…`). Trained on
    lock-time LineStar, so if anything optimistic as a stand-in for the live FP term;
  - MIXL (exploratory): + 0.10 × LAG, the live fallback.
- **Preregistration:** `reports/2026-10-06-prereg-study29-ownership-term.md` (frozen `44185227`).
- **Panel:** 36 slates (2023–24; no predictions exist for 2022), banks 1427/1428; B 20,000, seed 20261011; two-sided
  0.95.
- **Read and reproduced.** Read by the reviewer; **reproduced byte-identically by the laptop** (reader `3cd9fc73`;
  READ `fc5f6d23`). Lab: nfl2 `production/s29-ownership-term-20261006`.

**Reader output (verbatim):**
```
STUDY 29 READER  sha256 3cd9fc73396414674a20d728f12ec2bc0d1a1da7849708e27a3888b06485ac3e
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (MIX); POSITIVE favours the arm.
slates 36  banks [1427, 1428]  B 20000  seed 20261011  primary two-sided 0.95 (one decision arm), guard 1 one-sided 0.95 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 29 mean-track contests, 53 entries (26 in 21 big contests)  production row caps ['{"all": [11, 5]}']  BASE {"lam": 0.0}

== MIXT vs MIX  [DECISION]
  PRIMARY P(>= 1 big seat) per slate -0.06806  [-0.16441, +0.02602]  seasons 2023 -0.03214, 2024 -0.10398
  GUARD 1 mean entry pct +0.05060  one-sided lower +0.00947  (must exceed -0.015)
  GUARD 2 expected big seats 0.55146 vs MIX 0.77734  ratio 0.709  (must be >= 0.80)
  dealt identical to MIX: 0.000 of slate-banks
  ->  NO DIFFERENCE

== MIXL vs MIX  [EXPLORATORY (never decision-bearing)]
  PRIMARY P(>= 1 big seat) per slate -0.03965  [-0.12350, +0.04495]  seasons 2023 -0.06360, 2024 -0.01569
  GUARD 1 mean entry pct +0.01970  one-sided lower -0.00788  (must exceed -0.015)
  GUARD 2 expected big seats 0.75723 vs MIX 0.77734  ratio 0.974  (must be >= 0.80)
  dealt identical to MIX: 0.000 of slate-banks

secondaries (slate means):
  MIX P(>=1 big) 0.36194  expected big seats 0.77734  P(>=2 contests) 0.20239  slates P(>=1 big) < 1% 0.361  tickets 121.0  best>=200 0.139  entry pct 0.53061  worst-decile slate 0.24760  simulated P(>=1 big) 0.50311
      shape of dealt entries: pred_own_sum_lag 57.689  qb_game1_share 0.233  qb_game_top4_share 0.694  qb_games 3.583  qb_game_max_share 0.516  qb_plus1 0.547  bringback 0.543  dual 0.514  in_qb_game 3.097  games 4.746  max_entry_share 0.651
  MIXT P(>=1 big) 0.29388  expected big seats 0.55146  P(>=2 contests) 0.12481  slates P(>=1 big) < 1% 0.292  tickets 137.5  best>=200 0.042  entry pct 0.58121  worst-decile slate 0.34185  simulated P(>=1 big) 0.46106
      shape of dealt entries: pred_own_sum_lag 60.080  qb_game1_share 0.335  qb_game_top4_share 0.824  qb_games 3.444  qb_game_max_share 0.547  qb_plus1 0.547  bringback 0.541  dual 0.504  in_qb_game 3.115  games 4.798  max_entry_share 0.678
  MIXL P(>=1 big) 0.32229  expected big seats 0.75723  P(>=2 contests) 0.20649  slates P(>=1 big) < 1% 0.347  tickets 141.5  best>=200 0.083  entry pct 0.55031  worst-decile slate 0.31665  simulated P(>=1 big) 0.49693
      shape of dealt entries: pred_own_sum_lag 64.912  qb_game1_share 0.282  qb_game_top4_share 0.713  qb_games 3.556  qb_game_max_share 0.535  qb_plus1 0.547  bringback 0.543  dual 0.508  in_qb_game 3.115  games 4.717  max_entry_share 0.672
```

**Reading.**
1. **At the frozen rule MIXT vs MIX is NO DIFFERENCE** (the interval reaches +2.6). But both seasons are negative
   (−3.2 / −10.4), and guard 2 fails descriptively: expected big seats ×0.709, beyond his 20% tolerance.
2. **The chalk tilt trades CEILING for FLOOR** (MIX → MIXT):
   - mean finish .531 → .581; the worst decile .248 → .342;
   - but P(≥ 1 big) .362 → .294;
   - expected big seats .777 → .551;
   - best ≥ 200 .139 → .042;
   - P(≥ 2 contests) .202 → .125.

   It concentrates on the #1-total game's QBs (.233 → .335). The fallback (MIXL, LAG 0.10) is milder: −4.0 points,
   ×0.97.
3. **On the operator's first-place-only goal the term works against him.** It is RECOMMENDED OFF for Week 5
   (`UNION_MAIN_OWN_TILT` unset; reversible, class S, no code change). The operator decides (§5: NO DIFFERENCE → his
   choice, told plainly).
4. **Comparability:** MIX's absolute .362 is on the 36 slates of 2023–24, so it is not comparable with study 28's .296
   on 53.
5. **Transfer:** our projections, while the live term sits on FP's. The predictor is a stand-in.

## Addendum 135 (2026-10-06): study 30 (the Week-5 package against the status quo, on the operator's goal): NO DIFFERENCE at the frozen rule, both seasons negative, guard 1 fails descriptively — the direct test leans to the status quo, against the composition of studies 28 + 29

**Setup.**
- **Why:** studies 28 (the shape) and 29 (the term) each changed ONE stage. The post-selection law says a verdict does
  not transfer across a changed downstream stage, so the two COMPLETE constructions were compared directly.
- **Arms** (study 29's harness: caps 11 / 5, head, his Rev2 pins, our projections):
  - SQ (reference): the STATUS QUO, Week 4 as entered: the house shape (`PRODUCTION_STACK`) + 0.20 × TABPFN_LS
    predicted ownership % (the live term's stand-in; skill only);
  - PKG (DECISION): the PACKAGE recommended for Week 5: study 18's MIX (production `mix_rows`, pin-aware weights), NO
    term.
- **Preregistration:** `reports/2026-10-06-prereg-study30-package.md` (frozen `4996a53a`).
- **Panel:** 36 slates (2023–24), banks 1429/1430; B 20,000, seed 20261012; two-sided 0.95; guards as 18b.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `24108528`; READ `8dbdce26`; raw 1429 `767846fe`, 1430
    `09ec0394`.
  - The binding census was acked byte-identical (`773ff77d`).
  - Lab: nfl2 `production/s30-package-vs-status-quo-20261006`.

**Reader output (verbatim):**
```
STUDY 30 READER  sha256 2410852812c747fbad1e5e6a10d138d8fc56c58eeb528865a85eda309b0eb8d5
DIRECTION: P(>= 1 big seat) per slate from each dealt entry's share of the sampled field it BEATS (higher = better); every difference is ARM - its REFERENCE (SQ); POSITIVE favours the arm.
slates 36  banks [1429, 1430]  B 20000  seed 20261012  primary two-sided 0.95 (one decision arm), guard 1 one-sided 0.95 at -0.015, guard 2 expected-big-seat ratio >= 0.80  plan 29 mean-track contests, 53 entries (26 in 21 big contests)  production row caps ['{"all": [11, 5]}']  BASE {"lam": 0.0}

== PKG vs SQ  [DECISION]
  PRIMARY P(>= 1 big seat) per slate -0.07113  [-0.18760, +0.05327]  seasons 2023 -0.04223, 2024 -0.10003
  GUARD 1 mean entry pct -0.05128  one-sided lower -0.09698  (must exceed -0.015)
  GUARD 2 expected big seats 0.61593 vs SQ 0.62702  ratio 0.982  (must be >= 0.80)
  dealt identical to SQ: 0.000 of slate-banks
  ->  NO DIFFERENCE

secondaries (slate means):
  SQ  P(>=1 big) 0.36549  expected big seats 0.62702  P(>=2 contests) 0.16773  slates P(>=1 big) < 1% 0.264  tickets 108.0  best>=200 0.069  entry pct 0.57387  worst-decile slate 0.32708  simulated P(>=1 big) 0.46539
      shape of dealt entries: pred_own_sum_lag 60.452  qb_game1_share 0.333  qb_game_top4_share 0.832  qb_games 3.250  qb_game_max_share 0.750  qb_plus1 0.000  bringback 1.000  dual 0.270  in_qb_game 4.000  games 4.318  max_entry_share 0.788
  PKG P(>=1 big) 0.29436  expected big seats 0.61593  P(>=2 contests) 0.16406  slates P(>=1 big) < 1% 0.444  tickets 112.5  best>=200 0.069  entry pct 0.52260  worst-decile slate 0.29473  simulated P(>=1 big) 0.50373
      shape of dealt entries: pred_own_sum_lag 57.369  qb_game1_share 0.246  qb_game_top4_share 0.714  qb_games 3.778  qb_game_max_share 0.526  qb_plus1 0.546  bringback 0.542  dual 0.511  in_qb_game 3.105  games 4.761  max_entry_share 0.667
```

**Reading.**
1. **At the frozen rule PKG vs SQ is NO DIFFERENCE** (the interval reaches +5.3). Both seasons are negative (−4.2 /
   −10.0). Guard 1 fails descriptively: mean finish −0.051, one-sided lower −0.097. Guard 2 holds (×0.982).
2. **The status quo leads on nearly everything** (SQ / PKG):
   - P(≥ 1 big) .365 / .294;
   - mean finish .574 / .523;
   - near-dead slates .264 / .444;
   - worst decile .327 / .295.

   Expected big seats are nearly equal (.627 / .616), and the in-sample simulation favours PKG (.465 / .504).
3. **It contradicts the composition of studies 28 and 29.**
   - Study 28 had MIX − C at +6.1; study 29 had the term on MIX at −6.8. Together they imply the package beats the
     status quo by about 13 points, if the term's effect transferred to the house shape.
   - The guard-1 direction IS consistent across all three (the term raises the mean finish); only the primary conflicts.
   - Bank noise is large: the same construction (MIX, no term, the same 36 slates) read .362 on banks 1427/28 and
     .294 here.
4. **By §5 (frozen), NO DIFFERENCE means the package rests on studies 28 and 29, offered as his preference.** With
   both seasons negative and guard 1 failing descriptively, the reviewer's recommendation changed: the package is NOT
   supported as an improvement, and the status quo is the safer Week-5 choice until **study 31** reads. Study 31 is
   the 2 × 2 (shape × term) in one co-run on six banks, on Rev3; it measures the interaction directly.
5. **Record repair (disclosed in study 31's prereg; corrected by the laptop):** studies 24–30 imported production's
   `enter_layout` from the checkout on `PYTHONPATH` without recording its version. Reconstructed, not recorded:
   - integration's `enter_layout.py` was `fb2bf404…` (`e9ed88f1`, 09-30) until 10-06 05:03 CDT;
   - then `2851f7cf…` (`994590ea`), which only adds a refusal of pinned plans under the sequential / top layouts and
     never fires under head.
   - Every study dealt under head, and study 24's all-distinct arm (the one sequential path) ran on a plan without
     pins, so the two versions are behaviourally identical for 24–30.
   - The reviewer's runs imported `fb2bf404` (that checkout lacked `994590ea`). The laptop's byte-identical re-runs of
     29 and 30 imported `2851f7cf`. The two versions gave identical results.
   - Study 31 pins `3cb051ac` (`da399bdb`) and records it on every row.
6. **Transfer:** our projections, while the live build adds FP. The term's predictor is a stand-in. Study 30's reader
   docstring names the Rev1 plan file; the runs used Rev2 (`00c66004…`, checked by the reader's plan-sha gate). The
   frozen reader is unchanged.

## Addendum 136 (2026-10-06): study 31 (shape × ownership term in one co-run, on the plan he will enter): MIX vs CT NO DIFFERENCE, both seasons negative; the term HELPED on both shapes (against study 29); the winners' mix WITH the term is highest on every endpoint; the 1–26 satellite spread raises P(≥ 1 ticket) on every book

**Setup.**
- **Why:** studies 28 + 29 implied the package (MIX, no term) beats the status quo by about 13 points; study 30 measured
  that comparison directly and read −7.1. This study put all four constructions in ONE co-run per slate-bank and
  averaged SIX banks per slate.
- **Arms** (study 29's harness):
  - C: the house shape (`PRODUCTION_STACK`), no term;
  - CT: the house shape + 0.20 × TABPFN_LS predicted ownership % (the STATUS QUO, Week 4 as entered);
  - MIX: study 18's MIX (production `mix_rows`, pin-aware weights from Rev3's pins), no term (the PACKAGE);
  - MIXT: MIX + the same term.
- **Plan:** the operator's Rev3 (his 26 $20-ticket super-satellite entries spread over rows 1–26; `3dd19d6c…`).
  - K 26, caps 13 / 6, head.
  - Production `enter_layout` pinned `3cb051ac…` (`da399bdb`, a pin may add rows) and recorded on every row.
- **Preregistration:** `reports/2026-10-06-prereg-study31-factorial.md` (frozen `7d22756e`).
- **Panel:** 36 slates (2023–24), banks 1431–1436; B 20,000, seed 20261013; two-sided 0.95; guards as 18b.
- **Census:** the binding census on 1406 (36/36) and the confirmatory census (216/216) both passed every frozen check.
  - MIX / MIXT cells within 3 points of the quotas;
  - no short books;
  - no arm identical to its reference.
  - The Rev2 re-deal moves a 2-entry Wildcat on 5 of 432 house slate-banks (the overlap limit's wider wrap at K 26).
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `80b61bab`; READ `2d63a92d`; raw 1431 `3557c8bd` … 1436
    `e763f60f`; confirmatory census `c0105d02`.
  - Lab: nfl2 `production/s31-factorial-20261006`.

**Reader output (verbatim):**
```
STUDY 31 READER  sha256 80b61bab99f0a6166c70651835f3fc8186736aa5dd5fb0d074d92c9a06e43b79
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1431, 1432, 1433, 1434, 1435, 1436]  B 20000  seed 20261013  primary MIX - CT two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80  plan 29 contests, 53 entries; 7 $20-ticket super-satellites

== MIX vs CT  [DECISION: the package vs the status quo]
  PRIMARY P(>= 1 big seat) per slate -0.03636  [-0.13997, +0.06282]  seasons 2023 -0.06993, 2024 -0.00280
  GUARD 1 mean entry pct -0.04098  one-sided lower -0.07636  (must exceed -0.015)
  GUARD 2 expected big seats 0.63399 vs CT 0.59689  ratio 1.062  (must be >= 0.80)
  dealt identical: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY contrasts (never decision-bearing)
  CT - C (the term on the house shape): +0.09695  [-0.00800, +0.20033]  seasons 2023 +0.11740, 2024 +0.07650
  MIXT - MIX (the term on MIX): +0.05839  [-0.03147, +0.15635]  seasons 2023 +0.11876, 2024 -0.00198
  MIX - C (the shape without the term): +0.06059  [-0.02978, +0.15460]  seasons 2023 +0.04747, 2024 +0.07371
  MIXT - CT (the shape with the term): +0.02203  [-0.03791, +0.08176]  seasons 2023 +0.04883, 2024 -0.00478
  INTERACTION (MIXT - MIX) - (CT - C): -0.03856  [-0.13945, +0.06181]

secondaries (slate means):
  C    P(>=1 big) 0.24694  expected big seats 0.49970  P(>=2 contests) 0.12461  entry pct 0.51284
  CT   P(>=1 big) 0.34389  expected big seats 0.59689  P(>=2 contests) 0.14572  entry pct 0.56871
  MIX  P(>=1 big) 0.30753  expected big seats 0.63399  P(>=2 contests) 0.15412  entry pct 0.52773
  MIXT P(>=1 big) 0.36591  expected big seats 0.68288  P(>=2 contests) 0.16186  entry pct 0.57485

the operator's super-satellite question ($20-Milly-ticket super-satellites; descriptive; the same books dealt both ways):
  C    SPREAD 1-26 (the plan): P(>=1 ticket contest) 0.5512  expected tickets 1.8775  P(>=2 contests) 0.3634   REV2 PINS 1-5: 0.2776 / 1.3943 / 0.2048
  CT   SPREAD 1-26 (the plan): P(>=1 ticket contest) 0.7541  expected tickets 2.4012  P(>=2 contests) 0.4983   REV2 PINS 1-5: 0.5262 / 2.4775 / 0.4003
  MIX  SPREAD 1-26 (the plan): P(>=1 ticket contest) 0.6022  expected tickets 2.2287  P(>=2 contests) 0.4151   REV2 PINS 1-5: 0.4387 / 2.0425 / 0.3590
  MIXT SPREAD 1-26 (the plan): P(>=1 ticket contest) 0.7247  expected tickets 2.4852  P(>=2 contests) 0.5294   REV2 PINS 1-5: 0.5338 / 2.3716 / 0.3866
```

**Reading.**
1. **DECISION (MIX vs CT) is NO DIFFERENCE at the frozen rule** (the interval reaches +6.3). Both seasons are
   negative (−7.0 / −0.3), and guard 1 fails descriptively (mean finish −0.041, lower −0.076). By §5 (frozen), the
   package is not shown worse, so MIX stays his preference option. Read with the next item, though: MIX without the
   term trails the status quo on the primary and on mean finish.
2. **The ownership term HELPED on both shapes** (exploratory):
   - CT − C: +0.097 [−0.008, +0.200], both seasons positive;
   - MIXT − MIX: +0.058 [−0.031, +0.156];
   - the interaction: −0.039 [−0.139, +0.062], so there is no evidence the term's effect depends on the shape.

   **This does not replicate study 29** (MIXT − MIX −0.068 on 2 banks).
   - The two studies differ in BANKS (2 vs 6) and in PLAN / K: Rev2 at K 22, caps 11 / 5 vs Rev3 at K 26, caps 13 / 6.
     So the sign change is bank noise, K-dependence, or both (the laptop's caveat), not bank noise alone.
   - Study 31 is on the plan he enters, with three times the banks; study 29's recommendation (term OFF) is
     withdrawn.
3. **The winners' mix WITH the term (MIXT) is highest on every endpoint** (P(≥ 1 big) .366, expected big seats .683,
   P(≥ 2) .162, entry pct .575).
   - Against the status quo: +0.022 [−0.038, +0.082]; expected big seats ×1.14; mean finish +0.006. Exploratory, not
     a tested gain.
   - The shape alone (MIX − C +0.061) repeats study 28's +0.061.
4. **Recommendation for Week 5 (the operator decides):**
   - the term ON at 0.20 (the live predictor is FP's ownership projection, not this stand-in);
   - MIXT as his preference option, matching "play like the winners";
   - CT (Week 4 as entered) as the safe alternative;
   - plain MIX not to be armed without the term.
   - The laptop rehearsed MIXT end to end at K 26 (preview `71c0e4d5`): every check passed.
5. **The super-satellite secondary (descriptive; the same book dealt both ways).** Rev3's spread over rows 1–26
   against Rev2's pins on rows 1–5:
   - P(≥ 1 contest with a ticket) is higher on every book: C .55 / .28, CT .75 / .53, MIX .60 / .44, MIXT .72 / .53;
   - P(≥ 2) is higher on every book;
   - expected tickets are higher on C, MIX and MIXT, and about equal on CT (2.40 / 2.48).
   - His 1–26 instinct is supported on what he asked for: more chances of at least one ticket.
6. **Transfer:** our projections (the live build takes FP's), the term's predictor is a stand-in, and the fields are
   sampled from the Millionaire's ownership.

## Addendum 137 (2026-10-06): study 32 (choosing the best few lineups for a big contest): OFFER R4 at the frozen rule, marginal — with one entry no rule beats a random pick; with 2–3 entries choosing them TOGETHER (joint coverage) beats random, about +7 points at three entries; every one-row ranking rule trails random again

**Setup.**
- **Why:** the operator (10-06): "we NEED to have a way to sort lineups … i will have a limited number of entries to
  big contests next week, so we need to figure out how to choose the best ones." Every past ranking attempt failed (A13,
  A62, A93, A114, study 18).
- **The choice:** m of the K-26 book's entered rows (study 31's harness; Rev3, caps 13 / 6, `enter_layout`
  `3cb051ac`), for this week's lobby targets:
  - the $4,444 MEGA (N 634; S_big 119, every paid place; S_top 54);
  - the $333 Wildcat (N 4,170; S_big 1,000; S_top 270);
  - m = 1, 2, 3.
- **Books:** CT and MIX.
- **Rules:**
  - R0: book order;
  - R1: projected mean;
  - R2: simulated P(top S) one row at a time;
  - R3: simulated q99;
  - R4: JOINT coverage, the exhaustive m-subset maximizing simulated P(at least one in the top S), on 1,000 worlds
    against a PRE-LOCK field (TABPFN_LS ownership);
  - R5: breadth (distinct QBs / games);
  - RND: exact uniform-random, the control.
- **The operator's line:** his "big" inside next week's targets is "$500 or more", so S_big is the primary.
- **Preregistration:** `reports/2026-10-06-prereg-study32-sorting.md` (frozen `ec8c64ff`; the laptop's amendment: OFFER
  also needs R4 − R0 ≥ 0).
  - Deviation note 1 at the binding census, before any scored bank: when the pre-lock field cannot be sampled (the
    predicted ownership overflows the cap), 10,000 direct draws. It fired on 1 of 36 census slate-banks and 6 of 216
    scored, all six banks of 2023 W11.
- **Panel:** 36 slates, banks 1437–1442, B 20,000, seed 20261014, two-sided 0.95.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `c7abb741`; READ `f8a87773`; raw 1437 `c224631a` … 1442
    `b69a07c6`.
  - The descriptive output's body matched exactly. Its first header printed the reader's host path; it now prints the
    reader's sha256 (rule 2).

**Reader output (verbatim):**
```
STUDY 32 READER  sha256 c7abb741e0a620a8dd2abd57e5114636e6150ab1c858f24410d042ae5eef0f27
DIRECTION: realized P(the best chosen row is in the top S) per slate (the mean over its banks); every difference is RULE - REFERENCE; POSITIVE favours the rule.
slates 36  banks [1437, 1438, 1439, 1440, 1441, 1442]  B 20000  seed 20261014  primary R4 - RND over the 12 S_big cells, two-sided 0.95  targets {'MEGA': {'N': 634, 'S': {'big': 119, 'top': 54}}, 'WILD': {'N': 4170, 'S': {'big': 1000, 'top': 270}}}  m (1, 2, 3)

== R4 vs RND  [DECISION: joint coverage vs a uniformly random choice; S_big]
  PRIMARY realized P(best in the top S), pooled over 12 cells +0.02978  [+0.00081, +0.05986]  seasons 2023 +0.03444, 2024 +0.02511   (RND's level 0.41075)
  R4 - R0 (his default), pooled point estimate +0.04257  (OFFER needs >= 0)
  R4 picks exactly R0's rows in 0.057 of slate-bank-cells
  ->  OFFER R4

== EXPLORATORY (never decision-bearing)
  S_big R0 - RND: realized -0.01279  [-0.06679, +0.04052]  seasons 2023 +0.01467, 2024 -0.04025   simulated (in-sample) -0.00508
  S_big R1 - RND: realized -0.04765  [-0.09810, +0.00633]  seasons 2023 -0.06616, 2024 -0.02913   simulated (in-sample) -0.00927
  S_big R2 - RND: realized -0.04184  [-0.09365, +0.01122]  seasons 2023 -0.04902, 2024 -0.03467   simulated (in-sample) +0.00239
  S_big R3 - RND: realized -0.06550  [-0.13060, +0.00019]  seasons 2023 -0.06801, 2024 -0.06299   simulated (in-sample) -0.02048
  S_big R4 - RND: realized +0.02978  [+0.00081, +0.05986]  seasons 2023 +0.03444, 2024 +0.02511   simulated (in-sample) +0.08425
  S_big R5 - RND: realized -0.01521  [-0.07098, +0.04297]  seasons 2023 +0.01299, 2024 -0.04340   simulated (in-sample) +0.04014
  S_big R1 - R0 : realized -0.03486  [-0.07902, +0.00722]  seasons 2023 -0.08083, 2024 +0.01112   simulated (in-sample) -0.00419
  S_big R2 - R0 : realized -0.02905  [-0.07283, +0.01267]  seasons 2023 -0.06368, 2024 +0.00558   simulated (in-sample) +0.00747
  S_big R3 - R0 : realized -0.05271  [-0.10673, +0.00059]  seasons 2023 -0.08268, 2024 -0.02274   simulated (in-sample) -0.01540
  S_big R4 - R0 : realized +0.04257  [-0.00642, +0.09325]  seasons 2023 +0.01977, 2024 +0.06536   simulated (in-sample) +0.08933
  S_big R5 - R0 : realized -0.00242  [-0.06175, +0.05655]  seasons 2023 -0.00168, 2024 -0.00316   simulated (in-sample) +0.04522
  S_top R0 - RND: realized -0.01773  [-0.07167, +0.03733]  seasons 2023 -0.02269, 2024 -0.01276   simulated (in-sample) +0.00416
  S_top R1 - RND: realized -0.04108  [-0.08569, +0.00503]  seasons 2023 -0.05336, 2024 -0.02881   simulated (in-sample) +0.00164
  S_top R2 - RND: realized -0.04428  [-0.09537, +0.00880]  seasons 2023 -0.03440, 2024 -0.05415   simulated (in-sample) +0.01372
  S_top R3 - RND: realized -0.04453  [-0.09802, +0.01237]  seasons 2023 -0.03524, 2024 -0.05381   simulated (in-sample) -0.00251
  S_top R4 - RND: realized +0.00935  [-0.02286, +0.04631]  seasons 2023 +0.01493, 2024 +0.00377   simulated (in-sample) +0.07026
  S_top R5 - RND: realized +0.00249  [-0.03731, +0.04396]  seasons 2023 -0.01265, 2024 +0.01763   simulated (in-sample) +0.03803
  S_top R1 - R0 : realized -0.02336  [-0.06530, +0.01238]  seasons 2023 -0.03066, 2024 -0.01605   simulated (in-sample) -0.00251
  S_top R2 - R0 : realized -0.02655  [-0.07356, +0.01585]  seasons 2023 -0.01171, 2024 -0.04139   simulated (in-sample) +0.00957
  S_top R3 - R0 : realized -0.02680  [-0.07920, +0.02288]  seasons 2023 -0.01255, 2024 -0.04105   simulated (in-sample) -0.00666
  S_top R4 - R0 : realized +0.02707  [-0.03493, +0.09019]  seasons 2023 +0.03762, 2024 +0.01653   simulated (in-sample) +0.06610
  S_top R5 - R0 : realized +0.02022  [-0.03512, +0.07432]  seasons 2023 +0.01004, 2024 +0.03039   simulated (in-sample) +0.03388
  R4 - RND at S_big, by cell group:
    book CT      +0.04383  [+0.00446, +0.08478]
    book MIX     +0.01572  [-0.01163, +0.04428]
    target MEGA  +0.02712  [-0.00490, +0.06004]
    target WILD  +0.03243  [-0.00346, +0.06836]
    m 1          -0.00546  [-0.06165, +0.05322]
    m 2          +0.02556  [-0.01113, +0.06320]
    m 3          +0.06923  [+0.03233, +0.10500]

secondaries (slate means; realized level per rule at S_big, pooled over books, targets and m):
  R0  0.39796
  R1  0.36310
  R2  0.36891
  R3  0.34525
  R4  0.44052
  R5  0.39554
  RND 0.41075
  CT: Spearman(projected mean, realized percentile) within the book, slate mean +0.0467  (A62: +0.086)
  MIX: Spearman(projected mean, realized percentile) within the book, slate mean +0.0746  (A62: +0.086)
```

**Pre-stated descriptive lines (post-read, never decision-bearing; verbatim):**
```
STUDY 32 DESCRIPTIVE (post-read; pre-stated in §2b; never decision-bearing)  reader sha256 c7abb741e0a620a8dd2abd57e5114636e6150ab1c858f24410d042ae5eef0f27
  (1) R4 - R5 at S_big, 12 cells: +0.04498  [-0.00203, +0.09184]  seasons 2023 +0.02145, 2024 +0.06852
  (2) R4 - RND at S_big excluding fallback slate-banks (6 of 216; 35 slates kept): +0.03044  [+0.00097, +0.06134]  seasons 2023 +0.03607, 2024 +0.02511
```

**Reading.**
1. **At the frozen rule: OFFER R4.**
   - R4 − RND +0.030 [+0.001, +0.060], both seasons positive, R4 − R0 +0.043.
   - The lower bound only just clears 0: a marginal pass.
2. **The effect is entirely at m 2–3.**
   - m 1: −0.005 (R4 = R2 there).
   - m 2: +0.026 (not shown on its own).
   - m 3: +0.069 [+0.032, +0.105].
   - **With one entry, no rule beats a random pick.**
3. **One-row ranking fails again** (A62 holds).
   - R1 −0.048, R2 −0.042, R3 −0.066, R0 −0.013, R5 −0.015 against random.
   - The within-book Spearman is +0.047 (CT) / +0.075 (MIX).
   - Only choosing the SET for joint coverage gains, and R4 − R5 (+0.045 [−0.002, +0.092]) says the simulator adds
     something beyond "different QBs", not decisively.
4. **The simulator over-sells about 3×:** simulated +0.084, realized +0.030. The weekly R0-vs-R4 paired shadow is where
   this is watched.
5. **By book:** significant on CT (+0.044 [+0.004, +0.085]), not on MIX (+0.016 [−0.012, +0.044]).
   - **MIXT (the mix + term), the book he is most likely to arm, was not in study 32.** Its R4 edge is unmeasured,
     plausibly between the two.
   - §5's "the book he picks Friday" is therefore met only approximately.
6. **What it changes (frozen §5):** R4 becomes a reversible class-S selection step for next week's 1–3 entries in a big
   contest.
   - The laptop builds `choose_entries` (R4's rows beside R0 and RND; a parity test against the frozen `choose()`) and
     records a paired R0-vs-R4 shadow each week.
   - **No Week-5 change** (wording corrected by the laptop): this week's multi-entry contests are satellites whose
     lines study 32 did not test. They are the single-seat first-place ones, and the 25-seat $20-ticket
     super-satellites, which his Rev3 already deals on distinct rows. S_top, its deepest line, showed nothing: R4 − RND
     +0.009 [−0.023, +0.046].
7. **His plain answer:** "With 3 entries in the same big contest, choose them together by the simulator: about +7
   points of cash chance. With 2, about +3, not proven on its own. With 1, nothing beats a random pick."

## Addendum 138 (2026-10-06): study 33 (O-14 part 2: an injury-status calibration for late-window players, under a T-70 emulation): NO DIFFERENCE, leaning positive; every late Doubtful player in a reference book sat, but production already excludes Doubtful players at T-70; today's post-inactives rebuild is worth about +1.6 points; O-14 part 2 closes with no change

**Setup.**
- **Transfer, said first in the prereg:** with FP's projections live for every player, a PASS would change nothing in
  the Week-5 / 6 build. The study was LOW priority and run when the host was free.
- **The T-70 emulation in every arm:** every EARLY-window (13:00 ET) player not active on game day leaves the pool (the
  10:30 CT inactives list, the frame's `was_active`), and an early flagged player who was active keeps his mean.
- **The calibration (AV arms):** LATE-window (16:05 / 16:25 ET) Questionable / Doubtful players' means are multiplied
  by min(1, c_s' / c_H).
  - c_s is realized ÷ our mean per pre-lock stratum (Q × practice level, D), learned walk-forward (2022 → 2023;
    2022–23 → 2024) on the harness's own means at a fixed training seed, and shrunk toward the parent (k 100).
  - Late window: healthy c .844 / .906, Q .710 / .691, D .000.
  - Factors .73–.91.
- **Arms:** CT / AV_CT (the house shape + 0.20 term) and MIXT / AV_MIXT (the winners' mix + term). Exploratory: CT0 /
  MIXT0 without the T-70 step.
- **Plan and panel:** Rev3, K 26, caps 13 / 6, `enter_layout` `3cb051ac…`. 36 slates, banks 1443–1448, B 20,000, seed
  20261015.
- **Preregistration:** `reports/2026-10-06-prereg-study33-availability-calibration.md` (the laptop's draft and revisions
  after the reviewer's review; frozen `7f505dba`).
  - Participation is game-day active status (the inactives list), not snaps (corrected at the freeze).
- **Support census (= the binding census):** 5.8 late flagged players per slate. The reference books hold one on 44%
  (CT) / 42% (MIXT) of slate-banks; AV is identical to its reference on .39 / .47 (not vacuous).
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `9654d1b3`; READ `acfc7c33`; DESCRIPTIVE `7a81f70f`; raw
    1443 `379a2752` … 1448 `14334b5f`.
  - Lab: nfl2 `production/s33-availability-20261006`.

**Reader output (verbatim):**
```
STUDY 33 READER  sha256 9654d1b3abe320489e15cad5dd82a661eb4a37076b8abf0bd0a0b8cb72696c42
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1443, 1444, 1445, 1446, 1447, 1448]  B 20000  seed 20261015  primary AV - reference pooled over CT and MIXT, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80  factor table ['4e4607effa5c8f160d280c233358d3609a8d822a01ef0ddb834fc164835a1c3e']

== AV vs reference, pooled over the two shapes  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.01633  [-0.00454, +0.04145]  seasons 2023 +0.00591, 2024 +0.02675
  GUARD 1 mean entry pct +0.00592  one-sided lower +0.00131  (must exceed -0.015)
  GUARD 2 expected big seats 0.64324 vs 0.61829  ratio 1.040  (must be >= 0.80)
  AV dealt identical to its reference: 0.447 of slate-banks (pooled over shapes)
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  AV_CT - CT (calibration on the house shape): +0.02221  [-0.00245, +0.05350]  seasons 2023 +0.00165, 2024 +0.04278
  AV_MIXT - MIXT (calibration on the mix): +0.01045  [-0.00919, +0.03591]  seasons 2023 +0.01017, 2024 +0.01073
  CT - CT0 (the T-70 emulation on the house shape): +0.01713  [+0.00165, +0.03720]  seasons 2023 +0.00005, 2024 +0.03420
  MIXT - MIXT0 (the T-70 emulation on the mix): +0.01560  [+0.00353, +0.03041]  seasons 2023 +0.00604, 2024 +0.02515

secondaries (slate means):
  CT      P(>=1 big) 0.35283  expected big seats 0.62119  P(>=2) 0.16459  entry pct 0.57461  entries with a late flagged player 5.89  late flagged players dealt 0.59 (sat 0.12)
  AV_CT   P(>=1 big) 0.37505  expected big seats 0.66373  P(>=2) 0.17385  entry pct 0.58267  entries with a late flagged player 0.44  late flagged players dealt 0.10 (sat 0.02)
  MIXT    P(>=1 big) 0.33930  expected big seats 0.61538  P(>=2) 0.13591  entry pct 0.57561  entries with a late flagged player 4.16  late flagged players dealt 0.47 (sat 0.09)
  AV_MIXT P(>=1 big) 0.34975  expected big seats 0.62275  P(>=2) 0.13714  entry pct 0.57941  entries with a late flagged player 0.42  late flagged players dealt 0.08 (sat 0.01)
  CT0     P(>=1 big) 0.33571  expected big seats 0.59183  P(>=2) 0.15402  entry pct 0.56898  entries with a late flagged player 5.80  late flagged players dealt 0.60 (sat 0.12)
  MIXT0   P(>=1 big) 0.32370  expected big seats 0.59228  P(>=2) 0.12946  entry pct 0.57092  entries with a late flagged player 4.06  late flagged players dealt 0.47 (sat 0.09)
```

**Pre-stated descriptive line (post-read, never decision-bearing; verbatim):**
```
STUDY 33 DESCRIPTIVE (post-read; pre-stated in §5a; never decision-bearing)  reader sha256 9654d1b3abe320489e15cad5dd82a661eb4a37076b8abf0bd0a0b8cb72696c42
  CT      late D: dealt entries holding one 0.20 of 53, distinct players dealt 0.03 per slate-bank, of whom sat 1.000 (7 of 7)   late Q: dealt entries holding one 5.69 of 53, distinct players dealt 0.56 per slate-bank, of whom sat 0.149 (18 of 121)
  AV_CT   late D: dealt entries holding one 0.00 of 53, distinct players dealt 0.00 per slate-bank, of whom sat nan (0 of 0)   late Q: dealt entries holding one 0.44 of 53, distinct players dealt 0.10 per slate-bank, of whom sat 0.182 (4 of 22)
  MIXT    late D: dealt entries holding one 0.19 of 53, distinct players dealt 0.03 per slate-bank, of whom sat 1.000 (6 of 6)   late Q: dealt entries holding one 4.01 of 53, distinct players dealt 0.44 per slate-bank, of whom sat 0.146 (14 of 96)
  AV_MIXT late D: dealt entries holding one 0.00 of 53, distinct players dealt 0.00 per slate-bank, of whom sat nan (0 of 0)   late Q: dealt entries holding one 0.42 of 53, distinct players dealt 0.08 per slate-bank, of whom sat 0.118 (2 of 17)
  CT0     late D: dealt entries holding one 0.20 of 53, distinct players dealt 0.04 per slate-bank, of whom sat 1.000 (8 of 8)   late Q: dealt entries holding one 5.60 of 53, distinct players dealt 0.56 per slate-bank, of whom sat 0.149 (18 of 121)
  MIXT0   late D: dealt entries holding one 0.17 of 53, distinct players dealt 0.03 per slate-bank, of whom sat 1.000 (6 of 6)   late Q: dealt entries holding one 3.93 of 53, distinct players dealt 0.44 per slate-bank, of whom sat 0.137 (13 of 95)
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE**, leaning positive.
   - AV − reference +0.016 [−0.005, +0.041], both seasons positive.
   - Both guards hold: finish +0.006, expected big seats ×1.04.
   - **In plain words:** the calibration is small per player (1.7 points), but the selector drops a flagged player once
     he is slightly worse than his replacement. So AV in effect keeps late-window Q / D players out of the book (5.9 →
     0.4 dealt entries of 53 on CT).
2. **The Doubtful part is already live** (the laptop's correction, verified in code).
   - Every late Doubtful player dealt in a reference book sat: 7 of 7 (CT), 6 of 6 (MIXT), 8 of 8 (CT0).
   - Production has excluded DraftKings-status Doubtful players at T-70, in every window, since `81c1eabb`
     (2026-09-25): `r1c_sunday_reselect.OUT_STATUSES` includes D, and `union_reselect` drops them from every solve.
   - So the study's D gain is already captured live; the panel's references kept D players that live would have dropped.
   - Caveat: live keys on DraftKings' status field, the panel on the injury report's designation; they normally agree.
3. **The Questionable part is the open question, and it is NO DIFFERENCE.** About 15% of the late Q players dealt sat
   (18 of 121 on CT).
4. **Today's post-inactives T-70 rebuild is worth keeping:** CT − CT0 +0.017 [+0.002, +0.037], MIXT − MIXT0 +0.016
   [+0.004, +0.030]. These are the only intervals of the study that exclude 0. Live already does this.
5. **O-14 part 2 closes with no change** (frozen §7).
6. **MIXT vs CT** (not a designed contrast): here CT .353 vs MIXT .339 (calibrated .375 / .350), on other banks and with
   the T-70 emulation. Study 31 had MIXT .366 vs CT .344. **Together, tied within noise:** Friday's choice between them
   is his preference, not a measured edge. The decision sheet says so.
7. **Process:** the first training run stalled for 70 minutes without `OMP_THREAD_LIMIT=1`. It was re-run with the limit
   on the same inputs and seed, before any outcome.

## Addendum 139 (2026-10-06): study 34 (the max-entry regulars' habits as a selection tilt): NO DIFFERENCE — copying their visible habits, either where they differ from us or where we already agree, does not change his chance of a big win; their edge is pre-lock knowledge (projections), which FP now supplies

**Setup.**
- **The operator (10-06):** "do we feel that our ability to choose players - both stacks as well as boom players - is
  at a level comparable to the winners?", then "Do we have to wait until Thursday to test that?" Study 22a waits on the
  parked co-run and tests our old projection.
- **The evidence** (`reports/2026-10-05-regulars-player-choices.md`): the 117 max-entry regulars beat the rest of the
  Millionaire field by +6.1 points per lineup in Weeks 1–4 (null p 0.002). Our book was −3.8 (p 0.14).
- **The prior, stated first:** the report's §6 found that copying their visible habits did not carry the edge, so NO
  DIFFERENCE was expected.
- **Arms** (study 31's harness: Rev3, K 26, caps 13 / 6, `enter_layout` `3cb051ac…`, the 0.20 term):
  - **GAP (DECISION):** mean × (1 + 0.2·h_gap). h_gap tilts along their tilt MINUS ours on the BEHAVIOURAL features:
    the last played game's DK points −0.09, last week's opportunity share −0.06, the Questionable tag +0.05.
    - Value per $1k (−0.19) was excluded as a projection-difference artifact: it is measured on our projection, and FP
      closes it live.
  - **SHR (exploratory):** mean × (1 + 0.0125·h_shr), the three habits we already share (last game, salary change,
    early-season matchup samples).
  - **Each on CT and MIXT.**
- **Calibration (outcome-blind, fixed before it ran):**
  - Every z is in the report's units (over predicted-owned ≥ 0.2% players).
  - The GAP weights come from one per-feature reweighting, and β_gap 0.2 was the only grid value with every feature
    within 30% of its gap (1.02 / 0.88 / 0.89).
  - β_shr 0.0125 is the closest to the regulars' size (ratio 1.12).
  - On the scored banks: GAP 1.00 / 0.78 / 0.82, SHR 1.07.
- **Preregistration:** `reports/2026-10-06-prereg-study34-regulars-habits.md` (frozen `a3417b90`; the laptop's design:
  the GAP vector, value excluded, units, the landing rules).
- **Panel:** 36 slates, banks 1449–1454, B 20,000, seed 20261016. The binding census raw is `14879fd0…`.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `2da832bf`; READ `05dfad1b`; raw 1449 `a361d8f4` … 1454
    `8173b8a2`.
  - Lab: nfl2 `production/s34-regulars-habits-20261006`.

**Reader output (verbatim):**
```
STUDY 34 READER  sha256 2da832bf677315b166c5ed5941896ba466a600c697580e78c561c2faade6ca14
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1449, 1450, 1451, 1452, 1453, 1454]  B 20000  seed 20261016  primary GAP - reference pooled over CT and MIXT, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80  beta ['{"gap": 0.2, "shr": 0.0125}']

== GAP vs reference, pooled over the two shapes  [DECISION: the tilt toward the regulars along the gap]
  PRIMARY P(>= 1 big seat) per slate -0.00344  [-0.02968, +0.02329]  seasons 2023 -0.01987, 2024 +0.01298
  GUARD 1 mean entry pct -0.00313  one-sided lower -0.00904  (must exceed -0.015)
  GUARD 2 expected big seats 0.56991 vs 0.60583  ratio 0.941  (must be >= 0.80)
  GAP dealt identical to its reference: 0.000 of slate-banks (pooled over shapes)
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  SHR - reference pooled (the shared habits, more of them): -0.00879  [-0.06321, +0.04347]  seasons 2023 -0.03647, 2024 +0.01890
  GAP_CT - CT (the gap tilt on the house shape): -0.03063  [-0.07059, +0.00803]  seasons 2023 -0.04893, 2024 -0.01233
  GAP_MIXT - MIXT (the gap tilt on the mix): +0.02375  [-0.00437, +0.05156]  seasons 2023 +0.00920, 2024 +0.03830
  SHR_CT - CT (the shared habits on the house shape): -0.03585  [-0.10657, +0.03115]  seasons 2023 -0.04694, 2024 -0.02477
  SHR_MIXT - MIXT (the shared habits on the mix): +0.01828  [-0.03497, +0.07260]  seasons 2023 -0.02600, 2024 +0.06256
  pooled GAP - reference, weeks 2-5 (the matchup habit acts): +0.01130  [-0.00903, +0.03839]  slates 8
  pooled GAP - reference, weeks 6+: -0.00765  [-0.03975, +0.02598]  slates 28

secondaries (slate means):
  CT      P(>=1 big) 0.34277  expected big seats 0.59669  P(>=2) 0.15178  entry pct 0.57779  dealt entries' mean h_gap -0.0598  h_shr -1.1859
  GAP_CT  P(>=1 big) 0.31214  expected big seats 0.50506  P(>=2) 0.12058  entry pct 0.57217  dealt entries' mean h_gap -0.0530  h_shr -1.0595
  SHR_CT  P(>=1 big) 0.30692  expected big seats 0.51878  P(>=2) 0.12800  entry pct 0.56131  dealt entries' mean h_gap -0.0516  h_shr -0.8033
  MIXT    P(>=1 big) 0.32883  expected big seats 0.61498  P(>=2) 0.13010  entry pct 0.57962  dealt entries' mean h_gap -0.0622  h_shr -1.2042
  GAP_MIXT P(>=1 big) 0.35258  expected big seats 0.63476  P(>=2) 0.14450  entry pct 0.57897  dealt entries' mean h_gap -0.0551  h_shr -1.0745
  SHR_MIXT P(>=1 big) 0.34711  expected big seats 0.53404  P(>=2) 0.13454  entry pct 0.56674  dealt entries' mean h_gap -0.0541  h_shr -0.8186
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE.**
   - GAP − reference −0.003 [−0.030, +0.023]; seasons −0.020 / +0.013.
   - Both guards hold: finish −0.003, expected big seats ×0.94.
   - SHR −0.009 [−0.063, +0.043].
   - By shape, both tilts have opposite signs (GAP: CT −0.031, MIXT +0.024): noise around zero.
2. **Copying the regulars' visible habits at their size does not carry their edge,** whether where they differ from us
   or where we already agree. This confirms their report's §6: their edge is pre-lock knowledge, most likely better
   projections (in Week 4 they sided with FP).
   - From Week 5 FP's projections pick our lineups, which closes the largest known difference.
   - The weekly picks-vs-field line (merged 10-06) shows whether it worked.
3. **The books' habit LEVEL** (CT h_shr −1.18) is book against the owned pool. Projection books, like the whole field,
   take recent good scorers and salary risers. The arms tested a regulars-sized SHIFT on top of that; −1.18 does not
   mean "we do the opposite of the regulars" (the laptop).
4. **MIXT vs CT, a third reading** (not a designed contrast): CT .343 vs MIXT .329.
   - Across studies 31 / 33 / 34, MIXT − CT = +2.2 / −1.4 / −1.4 points (mean about −0.2).
   - Expected big seats MIXT / CT: 1.14 / 0.99 / 1.03.
   - Tied within noise. Friday's choice is his preference.
5. **Transfer:** the panel's means are ours; live, FP picks. The habits were tested on top of a projection-based book.

## Addendum 140 (2026-10-06): study 35 (QB diversity on the winners' mix: a per-QB cap at the regulars' level): NO DIFFERENCE, leaning positive on every endpoint in both seasons — the cap costs nothing measurable (unlike study 24's per-game cap) and is offered as his preference

**Setup.**
- **The operator (10-06):** "I'm more interested in the winner's mix than our way we've been doing it. However, it
  sounds like we're not getting the diversity of quarterbacks that we should be getting … I suspect … they look at the
  value of quarterbacks. And sometimes find a cheaper quarterback that has a good matchup."
- **What the data showed first** (2026 Weeks 1–4, descriptive):
  - The regulars have NO cheap-QB habit: share-weighted QB salary $5,878 vs the field's $5,961; their tilt against
    salary is +0.02.
  - They have NO good-matchup habit: they lean slightly away from small-sample soft matchups (−0.22).
  - They leaned toward the QBs FP rated above our model (+0.30, Week 4).
  - **The gap is CONCENTRATION, and it is new.** Our Weeks 1–3 QB spread matched the field. Week 4 put 60% on one QB;
    both Week-5 books put 51–59%. Each regular's most-used QB is in about 23% of his entries.
- **Arms** (study 31's harness: 36 slates, Rev3, K 26, caps 13 / 6, head, `enter_layout` `3cb051ac…`, the 0.20 term):
  - MIXT, the reference;
  - **MIXT_QA (DECISION):** a per-QB ROW cap of 5 (a QB is banned once in 5 rows, as the DST cap works);
  - MIXT_QB (exploratory): 8 rows.
  - The caps came from an outcome-blind calibration census: A is the loosest cap at or under a 25% most-used-QB share
    (5 rows: .223); B the loosest at or under 35% (8 rows: .323). The cost is −0.31 / −0.12 projected points per lineup.
  - Study 28's `mix_book` ran unchanged, with the capped builder swapped in.
- **Preregistration:** `reports/2026-10-06-prereg-study35-qb-cap.md` (frozen `c4fb005b`).
- **Panel:** banks 1455–1460, B 20,000, seed 20261017. The confirmatory census holds on the scored banks: QA .224
  (max .245), QB .323.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop:** reader `bf55070e`; READ `7edbf566`; raw 1455 `1984590a` … 1460
    `687c998f`.
  - Lab: nfl2 `production/s35-qb-cap-20261006`.
- **A cosmetic defect, disclosed:** the frozen reader's header line prints "STUDY 34 READER", a leftover from deriving
  it from study 34's reader. The sha identifies it, and the reader is unchanged.

**Reader output (verbatim):**
```
STUDY 34 READER  sha256 bf55070e56439a5f4a6bba23198ead737d6f05e989737674b6374c347bbbf69a
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1455, 1456, 1457, 1458, 1459, 1460]  B 20000  seed 20261017  primary MIXT_QA - MIXT, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80  QB row caps ['{"A": 5, "B": 8}']

== MIXT_QA vs MIXT  [DECISION: the per-QB cap at the regulars' level]
  PRIMARY P(>= 1 big seat) per slate +0.02563  [-0.02728, +0.08309]  seasons 2023 +0.02167, 2024 +0.02959
  GUARD 1 mean entry pct +0.00478  one-sided lower -0.00783  (must exceed -0.015)
  GUARD 2 expected big seats 0.61351 vs 0.58547  ratio 1.048  (must be >= 0.80)
  MIXT_QA dealt identical to MIXT: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_QB - MIXT (the milder QB cap): +0.02105  [-0.02407, +0.07048]  seasons 2023 +0.01233, 2024 +0.02976

secondaries (slate means):
  MIXT    P(>=1 big) 0.32495  expected big seats 0.58547  P(>=2) 0.12486  entry pct 0.57615  dealt top-QB share 0.474  effective QBs 2.81  distinct QBs 4.15
  MIXT_QA P(>=1 big) 0.35058  expected big seats 0.61351  P(>=2) 0.13967  entry pct 0.58093  dealt top-QB share 0.224  effective QBs 5.60  distinct QBs 6.75
  MIXT_QB P(>=1 big) 0.34600  expected big seats 0.63338  P(>=2) 0.14374  entry pct 0.58280  dealt top-QB share 0.323  effective QBs 3.91  distinct QBs 5.19
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE**, leaning positive.
   - MIXT_QA − MIXT +0.026 [−0.027, +0.083], both seasons positive (+0.022 / +0.030).
   - Both guards hold: finish +0.005, expected big seats ×1.05.
   - The milder cap: +0.021 [−0.024, +0.070], both seasons positive.
2. **Every endpoint leans the same way** (MIXT → QA): P(≥ 1 big) .325 → .351; expected big seats .585 → .614;
   P(≥ 2) .125 → .140; mean finish .576 → .581.
   - **Unlike study 24's per-GAME QB cap** (−1.8 points, failed his tolerance), the per-QB cap at the regulars' level
     costs nothing measurable. It is not a proven gain: the interval reaches −0.027.
3. **What it changes:** the most-used QB falls from .474 to .224 of the entries, and the distinct QBs rise from 4.2 to
   6.8. **It does not spread the rest of the book:** the top player's entry share stays .551 → .550 (the laptop).
4. **By frozen §4 (NO DIFFERENCE):** QB concentration is a feature without a measured cost or benefit, and he may
   choose the cap as a preference, told plainly.
   - **Recommended:** choose it. He asked for QB diversity, it matches the winners' level, nothing measured goes the
     wrong way, and it is reversible.
   - **Arming:** `UNION_MAIN_QB_CAP_ROWS=5 UNION_MAIN_QB_CAP_K=26` with MIXT. The production lever is
     `production/qb-cap-20261006` @ `b5514472`; its parity with the harness is confirmed (the ban at count ≥ cap, one
     running state, spares counted), and the union refuses any other K.
   - Friday's host rehearsal on the merged head checks the dealt most-used-QB share against the census level (.224 mean,
     .245 max).
5. **Transfer:** our projections (the live build uses FP's), the term's stand-in, the Millionaire's ownership field.

## Addendum 141 (2026-10-06): study 36 (less exposure to our most-used players: a stricter general player cap on the winners' mix with the QB cap): NO DIFFERENCE — the cap spreads the book but does not move P(≥ 1 big), and it costs average finish and projection; production's 0.5 cap stays recommended

**Setup.**
- **The operator (10-06), after agreeing to the recommended book** (the winners' mix + the ownership tilt + study 35's
  per-QB cap): "let's consider if we need to change the way it's still including the other most used player."
- **What the data showed first** (descriptive; aggregates only):
  - The regulars' most-used non-QB player is in .525 of their entries, about ours (.549).
  - **The difference is DEPTH.** Their 2nd / 5th / 10th sit at .431 / .296 / .205, with about 1.8 players over 40% of
    entries and 77 distinct non-QB players. Our recommended book has .537 / .510 / .402, 9.4 players over 40% and 26
    distinct.
  - Production's player cap (0.5 × K = 13 of 26 rows) binds for about ten players.
- **Arms** (study 35's harness unchanged: 36 slates, Rev3, K 26, DST cap 6, head, `enter_layout` `3cb051ac…`, the 0.20
  term, the per-QB cap of 5 rows in every arm):
  - MIXT_QA, the reference: production's player cap 0.5 (13 rows), the book he said yes to;
  - **MIXT_QAP (DECISION):** the general player cap at 0.35 (9 rows);
  - MIXT_QAP2 (exploratory): 0.40 (10 rows).
  - **The shares came from an outcome-blind calibration census.** A is the loosest share with at most 3 non-QB
    players over 40% of the dealt entries (the regulars' 75th percentile); B is the loosest with at most 6. The cost
    on paper is −1.33 / −0.95 projected points per lineup.
  - **Disclosed before freezing: a flat cap makes a plateau.** It does not reproduce the regulars' falling curve: at
    0.35 the top fifteen players sit near 35–39%, and the count over 30% rises from 11.5 to 14.8. The study therefore
    answers "less exposure to our most-used players", not "copy the regulars' curve".
  - The production lever exists: `UNION_MAIN_CAP` → `--main-cap-share`; the binding census asserted every row's caps
    equal production's floors.
- **Preregistration:** `reports/2026-10-06-prereg-study36-player-cap.md` (frozen `dcbe0668`).
- **Panel:** banks 1461–1466, B 20,000, seed 20261018.
  - The confirmatory census holds on the scored banks (216/216, code `b052a0e` clean, caps asserted on every row).
  - The most-used non-QB player: QA .549, QAP .394, QAP2 .433. Players over 40%: 9.47 / 0.17 / 3.72.
  - Projection against QA: −1.31 (QAP) and −0.93 (QAP2) per lineup.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop** (`cmp` clean): reader `f915e950`; READ `885ff890`; raw 1461
    `e8f98910` … 1466 `9c20f748`.
    - It used its own lab worktree detached at `de9b0f8`, with its own integration worktree's `src` (`enter_layout`
      `3cb051ac…`, the pin), so the reproduction does not share the reviewer's production path.
    - It checked the reader and experiment shas against the prereg pins, and the banks and plan against
      RAW_MANIFEST. It also checked that the confirmatory census (`b4f2433`, 12:07) was committed before the READ
      (`de9b0f8`, 12:11).
  - Lab: nfl2 `production/s36-player-cap-20261006`.

**Reader output (verbatim):**
```
STUDY 36 READER  sha256 f915e9504121c18b455a936fb0830b7f9dc10db7f929cfb469ac033956420381
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1461, 1462, 1463, 1464, 1465, 1466]  B 20000  seed 20261018  primary MIXT_QAP - MIXT_QA, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80  player-cap shares ['{"A": 0.35, "B": 0.4}']

== MIXT_QAP vs MIXT_QA  [DECISION: the stricter general player cap]
  PRIMARY P(>= 1 big seat) per slate -0.00041  [-0.08406, +0.09292]  seasons 2023 +0.03580, 2024 -0.03662
  GUARD 1 mean entry pct -0.02410  one-sided lower -0.04307  (must exceed -0.015)
  GUARD 2 expected big seats 0.69312 vs 0.64926  ratio 1.068  (must be >= 0.80)
  MIXT_QAP dealt identical to MIXT_QA: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_QAP2 - MIXT_QA (the milder player cap): +0.00278  [-0.06411, +0.07879]  seasons 2023 +0.02927, 2024 -0.02372

secondaries (slate means):
  MIXT_QA P(>=1 big) 0.37355  expected big seats 0.64926  P(>=2) 0.15460  entry pct 0.57750  dealt 2nd non-QB player 0.538  non-QB players over 40% 9.47  top QB 0.224
  MIXT_QAP P(>=1 big) 0.37314  expected big seats 0.69312  P(>=2) 0.16968  entry pct 0.55341  dealt 2nd non-QB player 0.384  non-QB players over 40% 0.17  top QB 0.223
  MIXT_QAP2 P(>=1 big) 0.37633  expected big seats 0.68575  P(>=2) 0.17334  entry pct 0.55842  dealt 2nd non-QB player 0.421  non-QB players over 40% 3.72  top QB 0.223
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE.**
   - MIXT_QAP − MIXT_QA −0.0004 [−0.084, +0.093]; the seasons split (+0.036 / −0.037).
   - The milder cap: +0.003 [−0.064, +0.079].
2. **Guard 1 is breached, and the breach is MEASURED** (not a cost on paper). The mean entry percentile falls from
   .578 to .553 (−0.0241; one-sided lower −0.0431, beyond the −0.015 margin).
   - **The guards gate a PASS only, per the frozen reader.** Its `verdict()` (unchanged since `e1d0304`, pinned by
     sha) evaluates them only inside the PASS branch (lower bound > 0, at most one negative season). A primary
     interval that spans 0 therefore reads NO DIFFERENCE whatever the guards show. Study 35's reader has the same
     structure.
   - **A text gap, disclosed (the laptop's audit):** §4 lists "PASS / FAIL (guard) / NO DIFFERENCE" without saying
     this. The code resolves it, and the verdict stands. **From study 37 on, §4 states in words that the guards gate a
     PASS only**, the same rule as the reader tests (the text must say what the code does).
   - The shortfall is reported as part of what the choice costs.
3. **Where the seats go:** expected big seats .649 → .693 (×1.07) and P(≥ 2) .155 → .170, while P(≥ 1) is flat
   (.374 → .373). A spread book adds seats on the weeks it already hits, not more weeks with a hit, and his goal is the
   weeks.
4. **What it changes:** the most-used non-QB player falls from .549 to .394 of the entries, and the players over 40%
   from 9.47 to 0.17. The QB cap is untouched (top QB .224 / .223).
5. **By frozen §5 (NO DIFFERENCE):** depth is his taste, told plainly what it costs: −1.31 projected points per lineup,
   and an average entry about 2.4 percentile points lower (the data cannot rule out 4.3).
   - **Recommended: keep production's 0.5 cap** (`UNION_MAIN_CAP` unset; the QB cap as armed). Nothing measured favours
     the spread on his goal, and the average-finish shortfall exceeds the margin we set. The laptop agrees.
   - **It is study 1b's pattern again.** At K 105 a ~30% cap cost mean finish while its ticket secondaries went the
     other way. A flatter book trades average finish for more seats in the weeks that hit, and does not move the
     number his goal counts.
6. **Transfer:** our projections (the live build uses FP's), the term's stand-in, the Millionaire's ownership field.

## Addendum 142 (2026-10-06): study 37 (the regulars' structure on the recommended book: more QB stacks and a steep player curve): NO DIFFERENCE at the frozen rule, but it leans worse on every endpoint and breaches both guards — spreading the players under our ratings costs, QB breadth alone is neutral; the yes-book stays, and the fair test is under FP's projections

**Setup.**
- **The operator (10-06):** "Is it because we aren't choosing suitable alternatives or because we suddenly are losing a
  stack because the QB has changed? Look closely at how the winners do it … Is their pool better only because of their
  volume? … I want to find a way to reduce my dependency on so many players while having suitable alternatives to
  pivot to."
- **What the data showed first** (descriptive, construction only; the laptop's analysis, reproduced by the reviewer):
  - **Study 36's cost was the alternatives, not the stacks.** A capped player's rows went to the next-best comparable
    player from anywhere on the slate, at the slate's base rate (2.0 / 5.3 / 92.7% same team / same game / another
    game, against 2.2 / 5.0 / 92.9% among comparable alternatives).
  - The QB cap unstacks our top receivers (with their own QB .271 → .212). The regulars' top receiver rides with his
    QB even less (.15), so that is no gap.
  - **Not volume:** at our size (random 26-lineup subsets of the 117 max-entry regulars' W1–4 portfolios) they hold
    11.3 QBs (the most-used at .219), 1.98 / 5.27 / 9.67 non-QB players over 40 / 30 / 20% and 53 distinct. Our book
    holds 6.75 / .19 / 9.5 / 11.8 / 13.6 / 25. Their alternatives are other stacks: the replacement for their most-used
    player comes from another game at the base rate, 2.4–3.2 points below him by our projections. Same-game swaps are
    not their habit (his doubt was right).
- **Arms** (study 35's harness: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`, the 0.20 term):
  - MIXT_QA, the reference: his yes-book (the QB cap of 5 rows, production's player / DST caps 13 / 6);
  - **MIXT_RS (DECISION):** the regulars' structure = QB tiers (a 6-row cap; at most 1 / 1 / 2 / 4 / 7 QBs reach
    6 / 5 / 4 / 3 / 2 rows) + non-QB tiers (at most 1 / 1 / 2 / 3 / 4 / 5 / 7 / 10 / 13 / 18 / 25 / 36 players reach
    13 … 2 rows);
  - MIXT_QBB and MIXT_NQC (exploratory): each tier set alone.
  - The tiers are the regulars' cohort medians at 26 rows, rounded half up, with no calibration grid
    (`scripts/s37_regulars_tiers.py`). QB r2 is exactly 6.50; the users with 26–40 entries sit at 6.30.
  - **A loud fallback:** a book row infeasible under the tiers is solved with the fewest tiers dropped, and recorded.
    It fired on 2 of the 216 scored slate-banks (RS, one row each, the r2 tier).
- **Preregistration:** `reports/2026-10-06-prereg-study37-regulars-structure.md` (frozen `d1ec7348`). Two findings
  before freezing were fixed and disclosed there (the book is the first 26 rows; the fallback).
- **Panel:** banks 1467–1472, B 20,000, seed 20261019. The confirmatory census holds on the scored banks: RS 11.03 QBs
  (.230), 2.23 / 5.27 / 10.45, 51.0 distinct; −2.17 projected points per dealt lineup (QBB −0.21, NQC −2.05).
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop** (`cmp` clean, its own worktree and production `src`): reader
    `2b1058de`; READ `73d77944`; raw 1467 `6539cdbf` … 1472 `4f9790f6`. The confirmatory census (`0ba54e2`) was
    committed before the READ (`32a3328`).
  - Lab: nfl2 `production/s37-structure-20261006`.

**Reader output (verbatim):**
```
STUDY 37 READER  sha256 2b1058dee6e648e48a1af034403705174c6460ca6b067ad2a32f385f0d9f9192
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1467, 1468, 1469, 1470, 1471, 1472]  B 20000  seed 20261019  primary MIXT_RS - MIXT_QA, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
MIXT_RS: QB cap 6 rows, QB tiers (rows, at most) [[6, 1], [5, 1], [4, 2], [3, 4], [2, 7]], non-QB tiers [[13, 1], [12, 1], [11, 2], [10, 3], [9, 4], [8, 5], [7, 7], [6, 10], [5, 13], [4, 18], [3, 25], [2, 36]]

== MIXT_RS vs MIXT_QA  [DECISION: the regulars' structure]
  PRIMARY P(>= 1 big seat) per slate -0.05097  [-0.13559, +0.03738]  seasons 2023 -0.00666, 2024 -0.09528
  GUARD 1 mean entry pct -0.04526  one-sided lower -0.06889  (must exceed -0.015)
  GUARD 2 expected big seats 0.52337 vs 0.70313  ratio 0.744  (must be >= 0.80)
  MIXT_RS dealt identical to MIXT_QA: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_QBB - MIXT_QA (the QB tiers only): -0.01543  [-0.05238, +0.02620]  seasons 2023 +0.01675, 2024 -0.04760
  MIXT_NQC - MIXT_QA (the non-QB tiers only): -0.08871  [-0.17090, -0.00033]  seasons 2023 -0.03941, 2024 -0.13802

secondaries (slate means; 'rows' = the 26 book rows, like-for-like with the regulars):
  MIXT_QA  P(>=1 big) 0.40595  expected big seats 0.70313  P(>=2) 0.16216  entry pct 0.57737  rows: QBs 6.78 top QB 0.192 non-QB over 40% 9.50 distinct non-QB 25.7  dealt top QB 0.224  dealt projection 127.07
  MIXT_RS  P(>=1 big) 0.35498  expected big seats 0.52337  P(>=2) 0.12533  entry pct 0.53212  rows: QBs 11.03 top QB 0.230 non-QB over 40% 2.23 distinct non-QB 51.0  dealt top QB 0.252  dealt projection 124.91
  MIXT_QBB P(>=1 big) 0.39052  expected big seats 0.66937  P(>=2) 0.16808  entry pct 0.57243  rows: QBs 11.00 top QB 0.231 non-QB over 40% 9.34 distinct non-QB 29.0  dealt top QB 0.252  dealt projection 126.86
  MIXT_NQC P(>=1 big) 0.31723  expected big seats 0.46974  P(>=2) 0.10428  entry pct 0.53680  rows: QBs 8.08 top QB 0.192 non-QB over 40% 2.23 distinct non-QB 50.8  dealt top QB 0.223  dealt projection 125.02
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE.** MIXT_RS − MIXT_QA −0.051 [−0.136, +0.037]; 2023 −0.007, 2024 −0.095. The
   upper bound keeps it off WORSE. The guards gate a PASS only.
2. **Both guards are breached, and measured.**
   - Guard 1: the mean entry percentile falls .577 → .532 (−0.045; lower −0.069).
   - Guard 2: expected big seats .703 → .523 (ratio 0.744). That is 26% fewer, beyond his own 20% tolerance.
   - Every endpoint leans the same way: P(≥ 1 big) .406 → .355; P(≥ 2) .162 → .125.
3. **Attribution (exploratory):**
   - **QB breadth alone is neutral**: QBB −0.015 [−0.052, +0.026], expected big seats .669. Study 35's step toward it
     leaned positive.
   - **The player curve carries the cost**: NQC −0.089 [−0.171, −0.0003], an interval that excludes 0, at −2.05
     projected points per lineup; expected big seats .470.
4. **Why it costs us and not them.** Spreading means playing one's second and third choices.
   - Under OUR ratings each spread-in player is rated lower, so the book loses finish and seats.
   - The regulars beat the field by +6.1 points per lineup WITH their spread, while ours runs −3.8 (the weekly
     picks-vs-field line, the laptop). The spread does not cost THEM: their alternatives are better than our model
     says (study 34: their edge is pre-lock knowledge, which FP now supplies).
   - This harness prices every alternative with our projections and cannot credit that.
5. **By frozen §5 (NO DIFFERENCE):** the structure is his taste, told plainly what it costs.
   - **Recommended: keep the yes-book** (the QB cap of 5 rows, player cap 0.5), and build no tier code. The laptop
     agrees.
   - What was said to him: "spreading under our ratings" is the problem, not "spreading". More QBs alone is harmless and
     adds nothing.
6. **The fair test is under the projections we use.** The proposal is study 38 (the reviewer's): a weekly PAPER co-run
   from Week 5. MIXT_RS and the yes-book are both built in the lab harness from the same pre-lock frame with FP's
   projections, never entered, and scored on Mondays against the real field beside the picks-vs-field and monkey lines.
   It is descriptive each week and pooled after 3–4 weeks under a rule frozen before Week 5's lock.
7. **Transfer:** our projections (the live build uses FP's), the term's stand-in, the Millionaire's ownership field,
   and the regulars' tiers from four 2026 weeks.

## Addendum 143 (2026-10-06): study 39 (an RB in the FLEX of every row on his live book): NO DIFFERENCE — a third running back in every lineup does not raise his chance of a big win; it costs 0.67 projected points per lineup and a tenth of the expected big seats; the 2-in-5 version is flat; his book stays as it is

**Setup.**
- **The operator (10-06):** "Do you see anything in what you just said that warrants a test now? I think more RBs in
  flex is a good start."
- **What the data showed first** (descriptive, aggregates):
  - The 117 regulars use 2.27–2.50 RBs per lineup (W1–4); his entered books 2.12–2.31. Their heavy core is about half
    RBs (the laptop's graph finding), workhorse goal-line backs that fit any QB stack. Our books use goal-line backs at
    least as much (goal-line share of the RBs used: ours .31–.59, theirs .32–.42).
  - **The prior, stated before any outcome:** in the 2026 W1–4 Millionaires the WINNING lineups held an RB in the FLEX
    LESS often than the field: top 0.1% 29%, top 1% 33%, the field 39%, our entries 30%.
- **Arms** (study 37's harness: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`; every arm the winners' mix, the
  QB cap of 5 rows, production's caps 13 / 6 and **his live objective, the mean with NO ownership term**):
  - MIXT_QA0, the reference: his live book;
  - **MIXT_RBF (DECISION):** every book row holds at least 3 RBs (one set constraint added to the optimizer for the
    arm's build; an infeasible row would fall back loudly, and never did);
  - MIXT_RBF40 (exploratory): the same rule on 2 of every 5 book rows.
- **Preregistration:** `reports/2026-10-06-prereg-study39-rb-flex.md` (frozen `f5708223`).
- **Panel:** banks 1473–1478, B 20,000, seed 20261020. The confirmatory census holds on the scored banks: RBF 3.00 RBs
  per book row (an RB in the FLEX on 100% of rows), RBF40 2.51 (51%), QA0 2.23 (23%); −0.67 / −0.20 projected points
  per dealt lineup; no fallbacks, no short books; dealt identically to the reference on 0.005 / 0.009 of slate-banks.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop** (rc 0, `cmp` clean, at lab `c3327c0`; raw files equal to the
    RAW_MANIFEST).
  - Reader `af500cc7`; READ `daa1ea30`; raw 1473 `ae444d95` … 1478 `9b2070ba`. The confirmatory census (`e780ab6`) was
    committed before the READ (`c3327c0`).
  - Lab: nfl2 `production/s39-rb-flex-20261006`.

**Reader output (verbatim):**
```
STUDY 39 READER  sha256 af500cc78050ca3c05f4c78049e2915d959b52a504d8bd1b9d50e3b6a3bf69ce
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1473, 1474, 1475, 1476, 1477, 1478]  B 20000  seed 20261020  primary MIXT_RBF - MIXT_QA0, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (rule, min RBs, QB cap, objective): [{"MIXT_QA0": null, "MIXT_RBF": "all", "MIXT_RBF40": "40"}, 3, 5, "player_mean (no ownership term)"]

== MIXT_RBF vs MIXT_QA0  [DECISION: an RB in the FLEX of every row]
  PRIMARY P(>= 1 big seat) per slate -0.01359  [-0.06456, +0.03902]  seasons 2023 -0.05451, 2024 +0.02732
  GUARD 1 mean entry pct -0.00223  one-sided lower -0.01783  (must exceed -0.015)
  GUARD 2 expected big seats 0.49906 vs 0.55189  ratio 0.904  (must be >= 0.80)
  MIXT_RBF dealt identical to MIXT_QA0: 0.005 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_RBF40 - MIXT_QA0 (the rule on 2 of every 5 rows): +0.00689  [-0.02345, +0.03794]  seasons 2023 +0.01023, 2024 +0.00355

secondaries (slate means):
  MIXT_QA0   P(>=1 big) 0.30690  expected big seats 0.55189  P(>=2) 0.14139  entry pct 0.52004  RBs per row 2.23  FLEX-RB rows 0.225  dealt top QB 0.224  dealt projection 128.48
  MIXT_RBF   P(>=1 big) 0.29331  expected big seats 0.49906  P(>=2) 0.12183  entry pct 0.51781  RBs per row 3.00  FLEX-RB rows 1.000  dealt top QB 0.223  dealt projection 127.81
  MIXT_RBF40 P(>=1 big) 0.31379  expected big seats 0.54770  P(>=2) 0.13102  entry pct 0.52067  RBs per row 2.51  FLEX-RB rows 0.514  dealt top QB 0.224  dealt projection 128.27
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE.** MIXT_RBF − MIXT_QA0 −0.014 [−0.065, +0.039]; 2023 −0.055, 2024 +0.027. The
   guards gate a PASS only.
2. **The guards, measured.** Guard 1 is breached at its bound (mean entry pct .520 → .518; lower −0.018). Guard 2 holds
   (expected big seats .552 → .499, ratio 0.904: a tenth fewer). P(≥ 2 big) .141 → .122. Every endpoint leans the same
   way, none decisively.
3. **The 2-in-5 version is flat** (exploratory): RBF40 +0.007 [−0.023, +0.038] at −0.20 projected points per lineup.
4. **Why.** The FLEX goes to the best remaining WR / TE by projection; forcing an RB there gives up 0.67 points per
   lineup, and the top-heavy contests pay the best lineups. That matches the prior: the winning lineups flexed an RB
   less often than the field, not more. The regulars' RB-led core is about WHICH backs (the workhorse, goal-line
   backs), which our books already use at least as much, not how many.
5. **By frozen §5 (NO DIFFERENCE):** his taste, told plainly what it costs. **Recommended: no RB-in-FLEX rule.** If he
   likes more backs, the 2-in-5 form costs nothing measurable on paper and adds nothing either.
6. **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field.

## Addendum 144 (2026-10-06): study 40 (fewer shared players between rows on his live book: at most 5 of 9 instead of 7): NO DIFFERENCE at the frozen rule, leaning positive on every endpoint at no measured cost — consistent with the outside review's real-field screen, and not against his decision to enter the 5 in Week 5

**Setup.**
- **The outside review (10-06)** screened seven one-setting levers on a fixed-book replay of Weeks 2–4 against the REAL
  Millionaire fields (`reports/2026-10-06-fixed-book-lever-screen-w2-w4.md`). `--mean-max-shared 5` (every union row
  shares at most 5 of 9 players with every earlier row; the live value was 7) read ahead on P(≥ 1 big seat) in W3
  (.310 against .009) and W4 (.343 against .034), level in W2 (.908 against .931). The laptop reproduced it
  byte-identically. The mechanism is the published one for top-heavy contests (an upper bound on the overlap with
  earlier entries; Hunter, Vielma and Zaman 2016). Three weeks with seven arms screened: a candidate, not a verdict.
- **The prior record, stated before any outcome:** studies 36–37 spread the book (exposure caps, the regulars' player
  curve) and leaned worse under our ratings; the lab's August overlap caps (008, 044) were null to negative on another
  objective and population.
- **His decision came first:** on the screen, he chose to ENTER the 5 in Week 5 (10-06, through the laptop), before
  this study was read. The harness is the second, independent source.
- **Arms** (study 39's harness: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`; every arm the winners' mix, the
  QB cap of 5 rows, production's caps 13 / 6 and his live objective, the mean with NO ownership term; the arms differ
  ONLY in the overlap limit, study 18's `MAX_SHARED`, which the cap builder reads at every solve, book rows and spares,
  as production's `--mean-max-shared`; every built row is checked against it):
  - MIXT_QA0, the reference: the live 7;
  - **MIXT_MS5 (DECISION):** at most 5 shared;
  - MIXT_MS6 (exploratory): at most 6 shared.
- **Preregistration:** `reports/2026-10-06-prereg-study40-max-shared.md` (frozen `902eccca`).
- **Panel:** banks 1479–1484, B 20,000, seed 20261021. The confirmatory census holds on the scored banks: shared players
  per pair of book rows 2.87 / 2.76 / 2.83 (pairs sharing 6+: 9.8% / 0 / 8.0%); QBs 6.93 / 7.64 / 7.16; distinct
  non-QB players 27.2 / 30.1 / 28.1; −0.06 / −0.01 projected points per dealt lineup; no short books; never identical to
  the reference.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop** (rc 0, `cmp` clean, at lab `e3bfb29`; raw files equal to the
    RAW_MANIFEST).
  - Reader `4bf0079d`; READ `09b58f75`; raw 1479 `d940cd78` … 1484 `c0543016`. The confirmatory census (`12a8665`) was
    committed before the READ (`e3bfb29`).
  - Lab: nfl2 `production/s40-max-shared-20261006`.

**Reader output (verbatim):**
```
STUDY 40 READER  sha256 4bf0079d7bde59ba4b2ac4657e5bf4d42c54cdb42935b0acd3350842f2150b50
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1479, 1480, 1481, 1482, 1483, 1484]  B 20000  seed 20261021  primary MIXT_MS5 - MIXT_QA0, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (max shared, QB cap, objective): [{"MIXT_MS5": 5, "MIXT_MS6": 6, "MIXT_QA0": 7}, 5, "player_mean (no ownership term)"]

== MIXT_MS5 vs MIXT_QA0  [DECISION: at most 5 shared players between rows]
  PRIMARY P(>= 1 big seat) per slate +0.02829  [-0.01167, +0.06735]  seasons 2023 -0.00840, 2024 +0.06499
  GUARD 1 mean entry pct +0.00576  one-sided lower +0.00194  (must exceed -0.015)
  GUARD 2 expected big seats 0.47331 vs 0.46084  ratio 1.027  (must be >= 0.80)
  MIXT_MS5 dealt identical to MIXT_QA0: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_MS6 - MIXT_QA0 (at most 6 shared): +0.02408  [-0.01237, +0.06217]  seasons 2023 -0.00477, 2024 +0.05293

secondaries (slate means):
  MIXT_QA0   P(>=1 big) 0.26591  expected big seats 0.46084  P(>=2) 0.10688  entry pct 0.51294  shared per pair 2.87  QBs 6.93  games 9.07  dealt top QB 0.223  dealt projection 128.42
  MIXT_MS5   P(>=1 big) 0.29421  expected big seats 0.47331  P(>=2) 0.10406  entry pct 0.51871  shared per pair 2.76  QBs 7.64  games 9.31  dealt top QB 0.221  dealt projection 128.37
  MIXT_MS6   P(>=1 big) 0.28999  expected big seats 0.51056  P(>=2) 0.13067  entry pct 0.51543  shared per pair 2.83  QBs 7.16  games 9.17  dealt top QB 0.221  dealt projection 128.41
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE, leaning positive.** MIXT_MS5 − MIXT_QA0 +0.028 [−0.012, +0.067]; 2023 −0.008,
   2024 +0.065. The lower bound is below 0, so it is not a PASS.
2. **The guards hold, and better than hold.** Guard 1: the mean entry percentile RISES .513 → .519 (lower +0.002).
   Guard 2: expected big seats .461 → .473 (ratio 1.027). P(≥ 1 big) .266 → .294. P(≥ 2) is level (.107 → .104).
3. **The 6 leans the same way** (exploratory): MS6 +0.024 [−0.012, +0.062], with the most expected seats (.511) and the
   highest P(≥ 2) (.131).
4. **Why it differs from the spreading that failed.** The exposure cap and the regulars' curve (studies 36–37) push the
   best players OUT of the top rows. The pairwise limit keeps them in half the book (the 13-row cap still binds) and
   only rearranges the tenth of row pairs that share 6–7 players, at 0.06 projected points per lineup: more distinct
   shots at almost the same mean.
5. **By frozen §5 (NO DIFFERENCE):** his taste, told what it costs on paper: nothing measurable, with a positive lean
   that matches the outside screen. **It does not argue against his decision to enter the 5 in Week 5**; Friday's
   rehearsal at 5 stays required before it touches an entry.
6. **Study 38 was amended before the Week-5 lock** (amendment 1): its paper arms now follow the live union's limit, and
   an exploratory MIXT_QA0_MS7 (his live book at the old 7) tracks the switch on the real field each week.
7. **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field; the
   outside screen is the real-field complement (three 2026 weeks).

## Addendum 145 (2026-10-06): study 41 (at most 4 shared players between rows, against his live 5): PASS — with study 40 the overlap limit reads 7 → 5 → 4 in one direction, and 4 is the knee (3 is level with 4 at four times the projection cost); recommended for Week 5 under three conditions

**Setup.**
- **From Week 5 his live book runs the overlap limit 5** (his 10-06 yes on the outside review's Weeks 2–4 screen).
  Study 40 (Addendum 144) read 5 against 7: NO DIFFERENCE, leaning positive (+0.028; the 6 alike, +0.024).
- **The question:** does a tighter limit add more, or has the gain plateaued? The operator, 10-06: "Please next proceed
  with anything you feel has a chance of helping."
- **The prior, stated before any outcome:** a plateau likely (the 6 read about as well as the 5; the lab's cap-4 prefix,
  044, was null on another objective).
- **Arms** (study 40's harness unchanged: 36 slates, Rev3, K 26, head, `enter_layout` `3cb051ac…`; every arm the winners'
  mix, the QB cap of 5 rows, production's caps 13 / 6, the mean with NO ownership term; the arms differ ONLY in the
  overlap limit, study 18's `MAX_SHARED` at every solve, book rows and spares; every built row checked):
  - MIXT_MS5, the reference: his live 5;
  - **MIXT_MS4 (DECISION):** at most 4 shared;
  - MIXT_MS3 (exploratory): at most 3 shared.
- **Preregistration:** `reports/2026-10-06-prereg-study41-max-shared4.md` (frozen `cc7c7f85`).
- **Panel:** banks 1485–1490, B 20,000, seed 20261022. The confirmatory census holds on the scored banks: shared
  players per pair of book rows 2.76 / 2.59 / 2.22; QBs 7.73 / 8.38 / 9.58; distinct non-QB players 30.1 / 33.2 / 38.6;
  −0.19 / −0.79 projected points per dealt lineup; no short books; never identical to the reference.
- **Read and reproduced:**
  - Read by the reviewer.
  - **Reproduced byte-identically by the laptop** (diff empty, at lab `cbeeb7c`, production `src` on the path; raw
    files equal to the RAW_MANIFEST).
  - Reader `a5dc8be7`; READ `9095e875`; raw 1485 … 1490 in the RAW_MANIFEST. The confirmatory census (`bbf14df`) was
    committed before the READ (`cbeeb7c`).
  - Lab: nfl2 `production/s41-max-shared4-20261006`.

**Reader output (verbatim):**
```
STUDY 41 READER  sha256 a5dc8be7b6d46dd5098039bedb33f5da1a6e065e81fdea44d98d4745297c7c42
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1485, 1486, 1487, 1488, 1489, 1490]  B 20000  seed 20261022  primary MIXT_MS4 - MIXT_MS5, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (max shared, QB cap, objective): [{"MIXT_MS3": 3, "MIXT_MS4": 4, "MIXT_MS5": 5}, 5, "player_mean (no ownership term)"]

== MIXT_MS4 vs MIXT_MS5  [DECISION: at most 4 shared players between rows, against the live 5]
  PRIMARY P(>= 1 big seat) per slate +0.05905  [+0.01096, +0.11176]  seasons 2023 +0.00993, 2024 +0.10818
  GUARD 1 mean entry pct -0.00381  one-sided lower -0.00902  (must exceed -0.015)
  GUARD 2 expected big seats 0.55250 vs 0.52991  ratio 1.043  (must be >= 0.80)
  MIXT_MS4 dealt identical to MIXT_MS5: 0.000 of slate-banks
  ->  PASS

== EXPLORATORY (never decision-bearing)
  MIXT_MS3 - MIXT_MS5 (at most 3 shared): +0.05505  [-0.00504, +0.11383]  seasons 2023 +0.02210, 2024 +0.08800

secondaries (slate means):
  MIXT_MS5   P(>=1 big) 0.30744  expected big seats 0.52991  P(>=2) 0.12655  entry pct 0.52614  shared per pair 2.76  QBs 7.73  games 9.29  dealt top QB 0.218  dealt projection 128.43
  MIXT_MS4   P(>=1 big) 0.36649  expected big seats 0.55250  P(>=2) 0.12776  entry pct 0.52233  shared per pair 2.59  QBs 8.37  games 9.42  dealt top QB 0.219  dealt projection 128.25
  MIXT_MS3   P(>=1 big) 0.36249  expected big seats 0.52365  P(>=2) 0.11963  entry pct 0.51534  shared per pair 2.22  QBs 9.58  games 10.07  dealt top QB 0.214  dealt projection 127.64
```

**Reading.**
1. **At the frozen rule: PASS.** MIXT_MS4 − MIXT_MS5 +0.059 [+0.011, +0.112]; both seasons positive (2023 +0.010, 2024
   +0.108). P(≥ 1 big seat) .307 → .366 per slate.
2. **The guards hold.** Guard 1: the mean entry percentile .526 → .522 (lower −0.009, inside the −0.015 margin). Guard
   2: expected big seats .530 → .553 (ratio 1.043). P(≥ 2) is level (.127 → .128).
3. **The curve.** Studies 40 and 41 together, on fresh banks each: 7 → 5 +0.028 (NO DIFFERENCE), 5 → 4 +0.059 (PASS),
   5 → 3 +0.055 (exploratory) at −0.79 projected points per lineup against −0.19 for the 4. The 4 is the knee: beyond it
   the projection cost grows and the gain stops.
4. **Why.** The limit keeps the best players in half the book (the 13-row cap still binds) and only forces every pair of
   rows to differ in more players, so the book takes more distinct shots (8.4 QBs against 7.7, more games) at almost the
   same mean. For one big seat, the best row matters, and more distinct rows give more chances at it.
5. **Multiplicity, said plainly.** Many studies have read these 36 slates. One PASS among them could be luck; what makes
   this more than that is the monotone trend across studies 40–41 on fresh banks, the outside review's real-field screen
   (Weeks 2–4) pointing the same way, and the mechanism.
6. **By frozen §5 (PASS):** the 4 is a candidate for his book. **Recommended for Week 5** if (1) the laptop's fixed-book
   check of Weeks 2–4 at 4 (the money-path rule's test) does not contradict it, (2) Friday's rehearsal runs at 4, and
   (3) study 38 is amended before the lock to accept 4; otherwise Week 6. His call.
7. **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field.

## Addendum 146 (2026-10-06): study 42 (the fill order: his best lineups first, or every shape for each QB?): both fills NO DIFFERENCE — the order the book is filled in is not where the big-win chance is; the value fill is not to be armed, the round-robin is his taste; and the overlap limit 4 over 5 replicated on fresh banks

**Setup.**
- **The operator (10-06):** "at one point this week we changed the way lineups are created so that we start with the best
  lineup for a QB so that others don't use up the available slots. Can you verify that we did that? Are we confident
  that we are putting our best strategy first for a given QB?" The laptop verified it was NOT done: production fills the
  MIX cells largest quota first (A1 8 → B 7 → C 7 → A2 4 at K 26), so a capped QB's 5 rows go to the earliest cells.
- **Two answers, one study** (his rule: a disagreement between agents becomes arms of one co-run study):
  - the reviewer's **value** fill: each step commits the best next row across the cells;
  - the outside reviewer's **round-robin**: one row per cell in turn, because in Weeks 2–4 the winning shape followed
    the game script, not the QB (`reports/2026-10-06-fill-order-replay-and-winners-shapes.md`).
- **Arms** (study 40's harness: 36 slates, Rev3, K 26, head; every arm his live book otherwise): a 3 × 2 of the fill
  (group = his live book / value / rr) by the overlap limit (4 / 5). The fill is `experiments/mix_fill.py` (shared with
  study 38, pinned `dcf6a299`); its group IS study 28's `mix_book` (parity tested on a scripted builder and on a real
  slate); production's `--mix-fill value` / `rr` are parity-pinned to its tests.
- **Disclosed:** the laptop's Weeks 2–4 real-field replays (value worse on the mean finish) were seen after the design and
  before the freeze.
- **Preregistration:** `reports/2026-10-06-prereg-study42-fill-order.md` (frozen `b68ffdd1`): TWO decisions (value − group,
  rr − group), each pooled over the limits, two-sided 0.975 each.
- **Panel:** banks 1491–1496, B 20,000, seed 20261023. The confirmatory census holds: capped QBs' rows in A1 .35–.39
  (group) → .18–.21 (value), .27–.28 (rr); dealt projection +0.07 (value), +0.4 (rr).
- **Read and reproduced:** read by the reviewer; **reproduced byte-identically by the laptop** (diff empty, at lab
  `9462d8a`; raw files equal to the RAW_MANIFEST). Reader `75062239`; READ `e14276fb`. The confirmatory census (`9cf2f1d`)
  was committed before the READ (`9462d8a`). Lab: nfl2 `production/s42-fill-order-20261006`.

**Reader output (verbatim):**
```
STUDY 42 READER  sha256 75062239cab424558af945d0483ba29d0ed18585ec5692f2393185eb0627167c
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1491, 1492, 1493, 1494, 1495, 1496]  B 20000  seed 20261023  two decisions (MIXT_VALUE, MIXT_RR), each against the group fill, pooled over the limits 4 and 5: primary two-sided 0.975 per decision, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms ((fill, max shared), QB cap, objective): [{"MIXT_GROUP4": ["group", 4], "MIXT_GROUP5": ["group", 5], "MIXT_RR4": ["rr", 4], "MIXT_RR5": ["rr", 5], "MIXT_VALUE4": ["value", 4], "MIXT_VALUE5": ["value", 5]}, 5, "player_mean (no ownership term)"]

== MIXT_VALUE vs MIXT_GROUP, pooled over the limits 4 and 5  [DECISION]
  PRIMARY P(>= 1 big seat) per slate -0.01493  [-0.06396, +0.03486] (two-sided 0.975)  seasons 2023 -0.04942, 2024 +0.01955
  GUARD 1 mean entry pct -0.00121  one-sided lower -0.00845  (must exceed -0.015)
  GUARD 2 expected big seats 0.53134 vs 0.55190  ratio 0.963  (must be >= 0.80)
  MIXT_VALUE dealt identical to MIXT_GROUP: 0.000 of slate-banks
  ->  NO DIFFERENCE

== MIXT_RR vs MIXT_GROUP, pooled over the limits 4 and 5  [DECISION]
  PRIMARY P(>= 1 big seat) per slate +0.00774  [-0.04024, +0.05611] (two-sided 0.975)  seasons 2023 -0.01831, 2024 +0.03379
  GUARD 1 mean entry pct +0.00509  one-sided lower -0.00075  (must exceed -0.015)
  GUARD 2 expected big seats 0.60197 vs 0.55190  ratio 1.091  (must be >= 0.80)
  MIXT_RR dealt identical to MIXT_GROUP: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  value at 4 (MIXT_VALUE4 - MIXT_GROUP4): -0.01881  [-0.06577, +0.02946]  seasons 2023 -0.05838, 2024 +0.02077
  value at 5 (MIXT_VALUE5 - MIXT_GROUP5): -0.01106  [-0.05959, +0.03896]  seasons 2023 -0.04045, 2024 +0.01832
  round-robin at 4 (MIXT_RR4 - MIXT_GROUP4): -0.00945  [-0.06093, +0.04411]  seasons 2023 -0.04327, 2024 +0.02436
  round-robin at 5 (MIXT_RR5 - MIXT_GROUP5): +0.02493  [-0.02106, +0.07288]  seasons 2023 +0.00664, 2024 +0.04321
  round-robin against value, pooled over the limits (MIXT_RR4 - MIXT_VALUE4 + MIXT_RR5 - MIXT_VALUE5): +0.02267  [-0.00301, +0.04799]  seasons 2023 +0.03110, 2024 +0.01424
  the limit 4 against 5, group fill: study 41 on fresh banks (MIXT_GROUP4 - MIXT_GROUP5): +0.04845  [+0.01796, +0.07916]  seasons 2023 +0.06352, 2024 +0.03337

secondaries (slate means):
  MIXT_GROUP4 P(>=1 big) 0.36069  expected big seats 0.56081  P(>=2) 0.12487  entry pct 0.51483  projection per book row 127.99  QBs 8.40  QBs at the cap 2.90  dealt projection 128.21
  MIXT_VALUE4 P(>=1 big) 0.34188  expected big seats 0.56379  P(>=2) 0.13138  entry pct 0.51374  projection per book row 127.98  QBs 8.20  QBs at the cap 2.89  dealt projection 128.29
  MIXT_RR4    P(>=1 big) 0.35123  expected big seats 0.60986  P(>=2) 0.15991  entry pct 0.52065  projection per book row 128.12  QBs 8.22  QBs at the cap 2.98  dealt projection 128.58
  MIXT_GROUP5 P(>=1 big) 0.31224  expected big seats 0.54299  P(>=2) 0.13088  entry pct 0.51691  projection per book row 128.18  QBs 7.74  QBs at the cap 3.37  dealt projection 128.38
  MIXT_VALUE5 P(>=1 big) 0.30118  expected big seats 0.49889  P(>=2) 0.12236  entry pct 0.51558  projection per book row 128.13  QBs 7.67  QBs at the cap 3.34  dealt projection 128.45
  MIXT_RR5    P(>=1 big) 0.33717  expected big seats 0.59407  P(>=2) 0.13487  entry pct 0.52127  projection per book row 128.28  QBs 7.50  QBs at the cap 3.42  dealt projection 128.79
```

**Reading.**
1. **Both decisions: NO DIFFERENCE.** Value − group −0.015 [−0.064, +0.035], leaning negative in 2023; rr − group +0.008
   [−0.040, +0.056]. Neither fill moves P(≥ 1 big seat).
2. **The value fill is not to be armed.** It leans negative here (both limits), its expected big seats fall (ratio
   0.963), and on the real Weeks 2–4 it lowered the mean finish (−0.05 at 5, −0.02 at 4).
3. **The round-robin is his taste.** Level on the main measure, it raises expected big seats by 9% (ratio 1.091) and the
   mean finish slightly, at no projection cost; rr beats value head to head (+0.023 [−0.003, +0.048], exploratory).
4. **The overlap limit, again.** GROUP4 − GROUP5 +0.048 [+0.018, +0.079], both seasons positive: study 41's PASS (+0.059)
   replicated on independent banks.
5. **The field audit** (the reviewer, 10-06; `reports/2026-10-06-field-audit-sampled-vs-real.md`): on the Weeks 2–4 replay
   books, fields drawn by the harness's own sampler from the real ownership rank every arm the way the real Millionaire
   fields do (18 of 18 contrast-weeks agree in sign; the mean-finish contrasts match to about 0.003), while their top
   lines run 3–6 points easier, so the harness's absolute chances are optimistic and its contrasts somewhat magnified in
   both directions. The 4's shortfall on the three real weeks is therefore not a field-model artifact: on those weeks the
   sampled fields say 4 < 5 too; it is those weeks' realized rows.
6. **Recommended:** the 4 for Week 5 (Friday's rehearsal at 4; study 38 amended to accept it); the group fill stays unless
   he prefers the round-robin; the value fill is not armed.
7. **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field whose top
   end is a little easier than the real one.

## Addendum 147 (2026-10-06): study 43 (a row in every high-total game): NO DIFFERENCE, leaning worse in both seasons — forcing a stack into each of the top games spends rows on weaker lineups and costs about a tenth of the expected big seats; the coverage switch stays off

**Setup.**
- **The operator (10-06):** "study 43 sounds the most interesting. I would like to try that first to be considered for
  this week." The idea: the outside review's §4.3 and the Week-4 post-mortem's "minimum exposure to every high-total
  game" -- the winning stack can sit in a game the book does not hold at all.
- **Arms** (study 42's harness: 36 slates, Rev3, K 26, head; the reference is his LIVE Week-5 book: the winners' mix,
  the overlap limit 4, the round-robin fill, the QB cap of 5 rows, caps 13 / 6, no ownership term):
  - MIXT_LIVE, the reference;
  - **MIXT_COVER4 (DECISION):** each of the slate's top-4 games by pre-lock total gets one A1 stack (QB + 2 + a
    bring-back) with its QB from that game, solved FIRST through the shared state and counted toward A1's quota; then
    the live fill; A1's rows then ordered by projection;
  - MIXT_COVER6 (exploratory): the top-6 games.
  - With no cover the fill IS study 42's frozen `mix_fill` (tested for every fill order).
- **Prior, stated first:** study 26's one-game shootout build read NO DIFFERENCE with a ceiling signal.
- **Preregistration:** `reports/2026-10-07-prereg-study43-game-cover.md` (frozen `e81122af`).
- **Panel:** banks 1497–1502, B 20,000, seed 20261024. The confirmatory census holds: the top-4 games holding an A1
  stack 2.11 (live) → 4.00; coverage rows 4 / 6, none missed; −0.21 / −0.31 projected points per dealt lineup.
- **Read and reproduced:** read by the reviewer; **reproduced byte-identically by the laptop** (diff empty, at lab
  `6392ca4`; raw files equal to the RAW_MANIFEST). Reader `88115e33`; READ `d830a305`. The confirmatory census
  (`95e2243`) was committed before the READ (`6392ca4`). Lab: nfl2 `production/s43-game-cover-20261006`.

**Reader output (verbatim):**
```
STUDY 43 READER  sha256 88115e33850b0a489a5e00956350fa2fb90860a2b5c34e777237355d21730588
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1497, 1498, 1499, 1500, 1501, 1502]  B 20000  seed 20261024  primary MIXT_COVER4 - MIXT_LIVE, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (cover k, live settings, QB cap, objective): [{"MIXT_COVER4": 4, "MIXT_COVER6": 6, "MIXT_LIVE": 0}, {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== MIXT_COVER4 vs MIXT_LIVE  [DECISION: the top-4 games by total each hold an A1 stack]
  PRIMARY P(>= 1 big seat) per slate -0.02840  [-0.06453, +0.00704]  seasons 2023 -0.02635, 2024 -0.03045
  GUARD 1 mean entry pct -0.00416  one-sided lower -0.00893  (must exceed -0.015)
  GUARD 2 expected big seats 0.58042 vs 0.65078  ratio 0.892  (must be >= 0.80)
  MIXT_COVER4 dealt identical to MIXT_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_COVER6 - MIXT_LIVE (the top-6 games): -0.00679  [-0.04872, +0.03431]  seasons 2023 +0.00813, 2024 -0.02172

secondaries (slate means):
  MIXT_LIVE   P(>=1 big) 0.34976  expected big seats 0.65078  P(>=2) 0.15562  entry pct 0.52327  top-4 held 2.11  top-6 held 2.81  QBs 8.09  games 9.48  dealt projection 128.62
  MIXT_COVER4 P(>=1 big) 0.32136  expected big seats 0.58042  P(>=2) 0.12917  entry pct 0.51912  top-4 held 4.00  top-6 held 4.55  QBs 8.90  games 9.73  dealt projection 128.41
  MIXT_COVER6 P(>=1 big) 0.34297  expected big seats 0.60895  P(>=2) 0.15024  entry pct 0.52096  top-4 held 4.00  top-6 held 6.00  QBs 9.52  games 9.96  dealt projection 128.31
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE, leaning worse.** COVER4 − LIVE −0.028 [−0.065, +0.007]; both seasons negative
   (2023 −0.026, 2024 −0.030).
2. **The guards hold, but the seats fall:** expected big seats .651 → .580 (ratio 0.892), P(≥ 2) .156 → .129. The mean
   finish is close (−0.004).
3. **Covering six games is level** (−0.007, exploratory): the cost of the forced rows is spread thinner.
4. **Why.** His live book already holds about half of the top-4 games; the other half are games the projection did not
   choose, and a stack forced into them is a weaker lineup taking a deal position from a stronger one.
5. **By frozen §5:** his book stays as it is; production's `--mix-cover-games` (reviewed) stays at 0, and study 38's
   parity refuses a nonzero cover (amendment 3).
6. **Transfer:** our projections (the live book uses FP's), realized 2023–24 outcomes against a sampled field whose top
   end is a little easier than the real one (the field audit).

## Addendum 148 (2026-10-06): study 45 (a contrarian insurance row): WORSE — the low-owned row is about a quarter as likely to win its single-seat satellite as the live row it replaces; not recommended

**Setup.**
- **The operator (10-06):** "This last week, I believe a contrarian play is what won ... let's consider you know, a one-off
  lineup a week or two where we do something like that." On the laptop's rule: "Yes, let's try what you described."
- **The descriptive read** (the laptop, the real W1–4 Millionaires): the winning lineup was less owned than the field in 3
  of 4 weeks; but the broad top 1% and top 100 were CHALKIER than the field in W1–3.
- **Arms** (study 43's harness; his live Week-5 book built once per slate-bank: the winners' mix, the limit 4, the
  round-robin fill, the QB cap of 5 rows, no ownership term):
  - MIXT_LIVE, the reference;
  - **MIXT_CON1 (DECISION):** rank 22 (its big entry: ONE single-seat satellite of 89; ranks 23–26 carry only $20
    supersats) holds a contrarian row: the best-projected A1 / B lineup whose QB is outside the slate's 8 most-owned QBs,
    with at least 3 skill players outside the 40 most-owned and the skill ownership summing to at most 0.70 × the live
    book's mean, within the caps and the limit 4;
  - MIXT_CON2 (ranks 21–22) and MIXT_CON1_R3 (rank 3), exploratory.
  - The rule is by rank and ratio: the harness's pre-lock ownership prediction (TABPFN_LS) ranks like the real
    ownership (r .82–.91) but is compressed; live the rule reads FP's projected ownership. Disclosed: the first,
    absolute-percent rule did not bind on the compressed predictions and was restated before the census.
- **Preregistration:** `reports/2026-10-06-prereg-study45-contrarian.md` (frozen `52b0f9a3`). The primary is the replaced
  position's big-seat chance (one row moves the book's P(≥ 1 big) by about that much); the book's P(≥ 1 big) beside it.
- **Panel:** banks 1503–1508, B 20,000, seed 20261025. The confirmatory census holds: contrarian rows feasible 99.5%;
  −1.17 projected points at rank 22; predicted skill ownership 51.7% against 72.7%; the QB about the 13th most-owned.
- **Read and reproduced:** read by the reviewer; **reproduced byte-identically by the laptop** (diff empty, at lab
  `e2d73a2`; raw files equal to the RAW_MANIFEST). Reader `ca403fb0`; READ `376d396d`. The confirmatory census (`6d4f422`)
  was committed before the READ (`e2d73a2`). Lab: nfl2 `production/s45-contrarian-20261006`.

**Reader output (verbatim):**
```
STUDY 45 READER  sha256 ca403fb000b272352e6a23cf04eb505f49cacdc5f6ee730b07ac9e75bee43994
DIRECTION: every difference is ARM - REFERENCE per slate (the mean over its banks); POSITIVE favours the first arm.
slates 36  banks [1503, 1504, 1505, 1506, 1507, 1508]  B 20000  seed 20261025  primary the replaced position's big-seat chance, MIXT_CON1 - MIXT_LIVE, two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (ranks replaced, live settings, contrarian rule, QB cap, objective): [{"MIXT_CON1": [21], "MIXT_CON1_R3": [2], "MIXT_CON2": [20, 21], "MIXT_LIVE": []}, {"fill": "rr", "max_shared": 4}, {"n_low": 3, "own_source": "TABPFN_LS", "qb_top_banned": 8, "skill_top_low": 40, "sum_ratio": 0.7}, 5, "player_mean (no ownership term)"]

== MIXT_CON1 vs MIXT_LIVE  [DECISION: a contrarian row at rank 22]
  PRIMARY the position's big-seat chance -0.01009  [-0.02178, -0.00205]  seasons 2023 -0.00228, 2024 -0.01790   (levels: contrarian 0.00278 vs live 0.01287)
  BOOK P(>= 1 big seat) per slate -0.00218  [-0.00481, -0.00019]  seasons 2023 +0.00002, 2024 -0.00438
  GUARD 1 mean entry pct -0.00313  one-sided lower -0.00505  (must exceed -0.015)
  GUARD 2 expected big seats 0.59028 vs 0.60037  ratio 0.983  (must be >= 0.80)
  MIXT_CON1 dealt identical to MIXT_LIVE: 0.005 of slate-banks
  ->  WORSE

== EXPLORATORY (never decision-bearing)
  MIXT_CON2 - MIXT_LIVE (two contrarian rows, ranks 21-22): positions' chance -0.02348  [-0.04798, -0.00147]  seasons 2023 -0.02033, 2024 -0.02664;  book P(>= 1 big) -0.00603  [-0.01740, +0.00517]
  MIXT_CON1_R3 - MIXT_LIVE (the contrarian row at rank 3): positions' chance -0.04463  [-0.10195, +0.00884]  seasons 2023 -0.04884, 2024 -0.04042;  book P(>= 1 big) -0.00835  [-0.02384, +0.00872]

secondaries (slate means):
  MIXT_LIVE    P(>=1 big) 0.35308  expected big seats 0.60037  P(>=2) 0.14020  entry pct 0.52602  dealt projection 128.58
  MIXT_CON1    P(>=1 big) 0.35090  expected big seats 0.59028  P(>=2) 0.13717  entry pct 0.52289  dealt projection 128.54
  MIXT_CON2    P(>=1 big) 0.34705  expected big seats 0.57689  P(>=2) 0.13139  entry pct 0.51909  dealt projection 128.50
  MIXT_CON1_R3 P(>=1 big) 0.34472  expected big seats 0.54471  P(>=2) 0.13004  entry pct 0.51393  dealt projection 128.33
```

**Reading.**
1. **At the frozen rule: WORSE.** The rank-22 position's chance of winning its satellite falls from 1.29% to 0.28% per
   slate (−0.0101 [−0.0218, −0.0021]); the book's P(≥ 1 big) −0.0022 [−0.0048, −0.0002].
2. **The exploratory placements agree:** two contrarian rows cost −0.023 on their positions; at rank 3 −0.045.
3. **Why.** A single-seat contest is won by the single top score. The contrarian row gives up projection (about 1.2
   points) without enough extra upside to top the field more often. This matches the real-field read: the top 1% runs
   chalkier than the field; the winners who were contrarian are the rarer route.
4. **By frozen §5 (WORSE):** the live row stays; no contrarian row for Week 5.
5. **Transfer, stated first:** the harness's field is sampled from the real ownership with 70% one-slot stacks; its
   top-end chalk is not calibrated to the real top 1% and its top line is 3–6 points easier (the field audit). A
   contrarian row's value depends on exactly that; the field calibration (study list item 40) is the check, and a
   reversal there would be reported. The gap here (about four to one) is large.

## Addendum 149 (2026-10-06): study 46 (half and half — his live book and the regulars' structure in one book): NO DIFFERENCE, leaning positive in both seasons — about +3 points of weekly P(≥ 1 big) and +6% expected big seats at about 1 point of mean finish; his taste, not proven

**Setup.**
- **The operator's standing directive (10-06, through the laptop):** "keep working on this until you figure out a
  strategy like that person's strategy that works". The person is a max-entry regular who won the Week-2 Millionaire
  (name private).
- **The laptop's per-lineup benchmark** on the real W1–4 Millionaires found:
  - the regulars' structure (study 38's RS0) finishes nearer him on average: W2–4 mean pct 51.2, against his 53.9;
  - our concentrated book finishes at 48.2, but it had our only top-1% week.
- **Study 37** put the regulars' structure on the whole book and leaned worse.
- **Arms.** The harness is study 43's, with his live Week-5 book as the reference: the winners' mix, limit 4,
  round-robin, QB cap 5, caps 13 / 6, no term.
  - **MIXT_HALF (DECISION).** 13 live rows are filled first. Then 13 rows are built under the regulars' tiers at 13
    lineups.
    - The tiers use study 37's method at the block's size, rounded half up.
    - They count the RS block's own rows only, with hard block caps (QB 3, non-QB 7).
    - An infeasible RS row uses study 37's loud fallback.
    - One builder state carries the global caps and the limit on every row.
    - The smaller block sits at positions ⌊(2i + 1) × 26 / (2n)⌋.
    - Each block is interleaved on its positions' head weights.
    - Spares are built without tiers.
  - **MIXT_THIRD** (9 RS rows) and **MIXT_TWOTHIRDS** (17) are exploratory.
  - With no RS rows the builder IS `mix_fill`'s round-robin. This holds on the scripted builder and on a real slate, 40
    of 40 rows.
- **The first study decided on the CALIBRATED field.** That is the sampler v2 of study-list item 40
  (`reports/2026-10-06-field-calibration-v2.md`). l02's field is scored beside it, drawn with the same seed.
- **Preregistration:** `reports/2026-10-07-prereg-study46-half-half.md` (frozen `e64c38c4`, sha256 `4ba0780e…`).
- **Panel:** banks 1509–1514, B 20,000, seed 20261026.
- **The confirmatory census holds:**
  - HALF has 10.25 QBs against 8.15, and 40.9 distinct players against 31.5;
  - 5.58 players sit over 40% of rows, against 7.59;
  - the live rows project 129.70 and the RS rows 125.12 per row (the live book: 128.12);
  - the projection cost is −0.65 per dealt lineup;
  - there were no relaxed rows, passes, drops or short books.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (diff empty, at lab
  `d48ff3c`; raw files equal to the RAW_MANIFEST).
  - Reader `8fb926b1`; READ `4578b611`.
  - The confirmatory census (`78a5b05`) was committed before the READ (`d48ff3c`).
  - Lab: nfl2 `production/s46-half-half-20261006`; LEDGER row `0842d07`.

**Reader output (verbatim):**
```
STUDY 46 READER  sha256 8fb926b198bff9fb8c7775e78f8863bb82f61bcf744677a163809fd843249b50
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1509, 1510, 1511, 1512, 1513, 1514]  B 20000  seed 20261026  primary MIXT_HALF - MIXT_LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (RS rows, RS tiers, live settings, QB cap, objective): [{"MIXT_HALF": 13, "MIXT_LIVE": 0, "MIXT_THIRD": 9, "MIXT_TWOTHIRDS": 17}, {"13": [3, [[3, 1], [2, 3]], 7, [[7, 1], [6, 2], [5, 4], [4, 7], [3, 12], [2, 22]]], "17": [4, [[4, 1], [3, 2], [2, 4]], 9, [[9, 1], [8, 2], [7, 3], [6, 4], [5, 7], [4, 11], [3, 17], [2, 27]]], "9": [3, [[3, 1], [2, 2]], 6, [[6, 1], [5, 1], [4, 3], [3, 7], [2, 15]]]}, {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== MIXT_HALF vs MIXT_LIVE  [DECISION: 13 regulars' rows + 13 live rows, one state; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.03170  [-0.00632, +0.06865]  seasons 2023 +0.04266, 2024 +0.02075
  GUARD 1 mean entry pct -0.00992  one-sided lower -0.01527  (must exceed -0.015)
  GUARD 2 expected big seats 0.53353 vs 0.50248  ratio 1.062  (must be >= 0.80)
  MIXT_HALF dealt identical to MIXT_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows): +0.01249  [-0.02743, +0.05313]  seasons 2023 +0.02643, 2024 -0.00144
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows): +0.02044  [-0.01723, +0.05934]  seasons 2023 +0.01979, 2024 +0.02108
  MIXT_HALF - MIXT_LIVE (13 regulars' rows, the l02 field): +0.02705  [-0.01040, +0.06432]  seasons 2023 +0.04081, 2024 +0.01328
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows, the l02 field): +0.00867  [-0.03286, +0.05075]  seasons 2023 +0.02730, 2024 -0.00996
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows, the l02 field): +0.01617  [-0.02223, +0.05612]  seasons 2023 +0.01657, 2024 +0.01578

the fields' lines (DK points, slate-bank means): v2 mean 128.11 p99 185.18 top-95 206.05  l02 mean 127.38 p99 183.71 top-95 204.65
secondaries (slate means; v2 = the calibrated field, l02 = studies 24-45's field):
  MIXT_LIVE       v2: P(>=1 big) 0.29794  expected big seats 0.50248  P(>=2) 0.11951  entry pct 0.51110  (live rows 0.51110, regulars' rows nan)
                  l02: P(>=1 big) 0.32728  expected big seats 0.56430  entry pct 0.51934  |  QBs 8.15  distinct 31.5  dealt projection 128.58
  MIXT_HALF       v2: P(>=1 big) 0.32965  expected big seats 0.53353  P(>=2) 0.12900  entry pct 0.50118  (live rows 0.53009, regulars' rows 0.47116)
                  l02: P(>=1 big) 0.35433  expected big seats 0.59564  entry pct 0.50929  |  QBs 10.25  distinct 40.9  dealt projection 127.93
  MIXT_THIRD      v2: P(>=1 big) 0.31044  expected big seats 0.50959  P(>=2) 0.12817  entry pct 0.50545  (live rows 0.52749, regulars' rows 0.46261)
                  l02: P(>=1 big) 0.33595  expected big seats 0.57529  entry pct 0.51360  |  QBs 8.97  distinct 37.7  dealt projection 128.06
  MIXT_TWOTHIRDS  v2: P(>=1 big) 0.31838  expected big seats 0.51306  P(>=2) 0.12752  entry pct 0.50407  (live rows 0.53212, regulars' rows 0.48964)
                  l02: P(>=1 big) 0.34345  expected big seats 0.57241  entry pct 0.51219  |  QBs 10.77  distinct 43.9  dealt projection 127.80
```

**Reading.**
1. **At the frozen rule: NO DIFFERENCE.** P(≥ 1 big seat) moved +0.0317 [−0.0063, +0.0687] (0.298 → 0.330), positive
   in both seasons.
   - Expected big seats rose 6%.
   - The mean finish fell about 1 point (guard 1's lower bound, −0.0153, sits just past −0.015). The guards gate a PASS
     only.
2. **The direction is consistent.** It holds in both seasons, on both fields (l02 +0.027), and in all three splits
   (THIRD +0.012, TWOTHIRDS +0.020; half is the best).
   - Study 37's whole-book version leaned the other way.
   - So a mix of the two constructions, not a copy of the regular, is what this harness likes. That matches his
     strategy-mix principle (10-05).
3. **Why it can help.** The live block keeps his best 13 rows; they finish higher than his whole book does (.530 against
   .511). The regulars' rows finish lower on average (.471), but they are more independent shots: more QBs, more
   players and fewer heavy exposures.
4. **The calibrated field reads the levels lower:** his live book's P(≥ 1 big) is .298 on v2, against .327 on l02.
   That is expected and closer to the real fields, not a regression.
5. **By frozen §5 (NO DIFFERENCE):** his taste, told the cost and the change. The production switch exists:
   - `--mix-rs-rows` / `UNION_MIX_RS_ROWS`, merged at integration `f70ce138`;
   - reviewed CLEAN and parity-pinned to the lab's scripted builder;
   - off.

   Turning it on for Week 5 needs four things:
   - the laptop's W2–4 real-field replay at 13;
   - study 38's amendment 5 before the lock (amendment 4 refuses a live regulars' block until then);
   - the gate checker's policy view;
   - Friday's rehearsal at 13.
6. **Multiplicity.** Many studies have read these 36 slates. A +0.032 whose interval touches 0 is suggestive, not proof.
   Study 38's live FP weeks and the weekly real-field benchmark are the checks that follow.

## Addendum 150 (2026-10-06): study 46c (the half-and-half book on the 2022 slates — the out-of-sample check): CONTRADICTS at the frozen go / no-go — the 2022 estimate is negative; the half book stays off for Week 5; pooled over 2022–24 it is a wash

**Setup.**
- **The trigger.** Study 46 (Addendum 149) read the half book NO DIFFERENCE, leaning positive in 2023–24. The
  operator's Week-5 answer (10-06, through the laptop) was "Yes, pending 2022 check".
- **The 2022 slates.** The 17 2022 k1 slates with real Millionaire ownership had never been read on this question.
  Studies 37–46 use 2023–24 because their ownership-PREDICTION arms need it; study 46's arms use none.
- **Disclosed:** proposed after study 46's read, as a confirmation.
- **The code.** Study 46's frozen experiment is imported, its sha `30647fef` asserted, with only the season guard
  opened to 2022. Its census and frozen reader (`8fb926b1`) are unchanged.
- **The go / no-go**, frozen before the read in the laptop's wording:
  - CONTRADICTS if the 2022 read is WORSE, or its point estimate of HALF − LIVE is below 0. Then `MIX_RS` stays 0.
  - Otherwise `MIX_RS=13` goes in.
- **Preregistration:** `reports/2026-10-07-prereg-study46c-half-half-2022.md` (frozen `f6baebd2`, sha256 `2f7982e3…`).
- **Panel:** banks 1509–1514 on the 2022 slates (never computed before), B 20,000, seed 20261026.
- **The confirmatory census holds:** QBs 7.76 / 10.12, distinct 33.0 / 42.2, −0.73 per dealt lineup; no relaxed rows,
  passes, drops or short books.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (diff empty, at lab
  `05b4580`; raw 2022 and pool files equal to the RAW_MANIFEST).
  - READ `e90b7afa`; pool READ `40574df4`.
  - The confirmatory census (`9dafd73`) was committed before the READ.
  - Lab: nfl2 `production/s46c-half-half-2022-20261006`; LEDGER row `7aebf46`.

**Reader output on the 2022 slates (verbatim; the PRIMARY):**
```
STUDY 46 READER  sha256 8fb926b198bff9fb8c7775e78f8863bb82f61bcf744677a163809fd843249b50
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 17  banks [1509, 1510, 1511, 1512, 1513, 1514]  B 20000  seed 20261026  primary MIXT_HALF - MIXT_LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (RS rows, RS tiers, live settings, QB cap, objective): [{"MIXT_HALF": 13, "MIXT_LIVE": 0, "MIXT_THIRD": 9, "MIXT_TWOTHIRDS": 17}, {"13": [3, [[3, 1], [2, 3]], 7, [[7, 1], [6, 2], [5, 4], [4, 7], [3, 12], [2, 22]]], "17": [4, [[4, 1], [3, 2], [2, 4]], 9, [[9, 1], [8, 2], [7, 3], [6, 4], [5, 7], [4, 11], [3, 17], [2, 27]]], "9": [3, [[3, 1], [2, 2]], 6, [[6, 1], [5, 1], [4, 3], [3, 7], [2, 15]]]}, {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== MIXT_HALF vs MIXT_LIVE  [DECISION: 13 regulars' rows + 13 live rows, one state; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate -0.02268  [-0.09830, +0.03754]  seasons 2022 -0.02268
  GUARD 1 mean entry pct -0.00020  one-sided lower -0.00772  (must exceed -0.015)
  GUARD 2 expected big seats 0.35806 vs 0.39961  ratio 0.896  (must be >= 0.80)
  MIXT_HALF dealt identical to MIXT_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows): -0.00438  [-0.08869, +0.06430]  seasons 2022 -0.00438
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows): -0.01734  [-0.07122, +0.02555]  seasons 2022 -0.01734
  MIXT_HALF - MIXT_LIVE (13 regulars' rows, the l02 field): -0.01789  [-0.09029, +0.04067]  seasons 2022 -0.01789
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows, the l02 field): -0.00079  [-0.08341, +0.06747]  seasons 2022 -0.00079
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows, the l02 field): -0.01492  [-0.06692, +0.02636]  seasons 2022 -0.01492

the fields' lines (DK points, slate-bank means): v2 mean 125.56 p99 185.61 top-95 208.46  l02 mean 124.83 p99 183.63 top-95 206.32
secondaries (slate means; v2 = the calibrated field, l02 = studies 24-45's field):
  MIXT_LIVE       v2: P(>=1 big) 0.26667  expected big seats 0.39961  P(>=2) 0.09926  entry pct 0.45221  (live rows 0.45221, regulars' rows nan)
                  l02: P(>=1 big) 0.28432  expected big seats 0.45052  entry pct 0.45950  |  QBs 7.76  distinct 33.0  dealt projection 132.77
  MIXT_HALF       v2: P(>=1 big) 0.24399  expected big seats 0.35806  P(>=2) 0.08183  entry pct 0.45201  (live rows 0.48936, regulars' rows 0.41322)
                  l02: P(>=1 big) 0.26643  expected big seats 0.41003  entry pct 0.45933  |  QBs 10.12  distinct 42.2  dealt projection 132.05
  MIXT_THIRD      v2: P(>=1 big) 0.26229  expected big seats 0.41107  P(>=2) 0.10541  entry pct 0.45409  (live rows 0.48489, regulars' rows 0.39421)
                  l02: P(>=1 big) 0.28353  expected big seats 0.46856  entry pct 0.46152  |  QBs 8.61  distinct 38.9  dealt projection 132.25
  MIXT_TWOTHIRDS  v2: P(>=1 big) 0.24933  expected big seats 0.36056  P(>=2) 0.08742  entry pct 0.45148  (live rows 0.48819, regulars' rows 0.43260)
                  l02: P(>=1 big) 0.26940  expected big seats 0.40825  entry pct 0.45890  |  QBs 10.63  distinct 44.0  dealt projection 132.03
```

**Reader output on the 53-slate pool (verbatim; EXPLORATORY, not a fresh test):**
```
STUDY 46 READER  sha256 8fb926b198bff9fb8c7775e78f8863bb82f61bcf744677a163809fd843249b50
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 53  banks [1509, 1510, 1511, 1512, 1513, 1514]  B 20000  seed 20261026  primary MIXT_HALF - MIXT_LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (RS rows, RS tiers, live settings, QB cap, objective): [{"MIXT_HALF": 13, "MIXT_LIVE": 0, "MIXT_THIRD": 9, "MIXT_TWOTHIRDS": 17}, {"13": [3, [[3, 1], [2, 3]], 7, [[7, 1], [6, 2], [5, 4], [4, 7], [3, 12], [2, 22]]], "17": [4, [[4, 1], [3, 2], [2, 4]], 9, [[9, 1], [8, 2], [7, 3], [6, 4], [5, 7], [4, 11], [3, 17], [2, 27]]], "9": [3, [[3, 1], [2, 2]], 6, [[6, 1], [5, 1], [4, 3], [3, 7], [2, 15]]]}, {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== MIXT_HALF vs MIXT_LIVE  [DECISION: 13 regulars' rows + 13 live rows, one state; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.01426  [-0.02018, +0.04642]  seasons 2022 -0.02268, 2023 +0.04266, 2024 +0.02075
  GUARD 1 mean entry pct -0.00680  one-sided lower -0.01111  (must exceed -0.015)
  GUARD 2 expected big seats 0.47724 vs 0.46949  ratio 1.017  (must be >= 0.80)
  MIXT_HALF dealt identical to MIXT_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows): +0.00708  [-0.03010, +0.04316]  seasons 2022 -0.00438, 2023 +0.02643, 2024 -0.00144
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows): +0.00832  [-0.02212, +0.03864]  seasons 2022 -0.01734, 2023 +0.01979, 2024 +0.02108
  MIXT_HALF - MIXT_LIVE (13 regulars' rows, the l02 field): +0.01263  [-0.02073, +0.04410]  seasons 2022 -0.01789, 2023 +0.04081, 2024 +0.01328
  MIXT_THIRD - MIXT_LIVE (9 regulars' rows, the l02 field): +0.00563  [-0.03151, +0.04234]  seasons 2022 -0.00079, 2023 +0.02730, 2024 -0.00996
  MIXT_TWOTHIRDS - MIXT_LIVE (17 regulars' rows, the l02 field): +0.00620  [-0.02439, +0.03673]  seasons 2022 -0.01492, 2023 +0.01657, 2024 +0.01578

the fields' lines (DK points, slate-bank means): v2 mean 127.30 p99 185.32 top-95 206.82  l02 mean 126.56 p99 183.69 top-95 205.18
secondaries (slate means; v2 = the calibrated field, l02 = studies 24-45's field):
  MIXT_LIVE       v2: P(>=1 big) 0.28791  expected big seats 0.46949  P(>=2) 0.11302  entry pct 0.49221  (live rows 0.49221, regulars' rows nan)
                  l02: P(>=1 big) 0.31350  expected big seats 0.52781  entry pct 0.50015  |  QBs 8.03  distinct 32.0  dealt projection 129.92
  MIXT_HALF       v2: P(>=1 big) 0.30217  expected big seats 0.47724  P(>=2) 0.11387  entry pct 0.48541  (live rows 0.51702, regulars' rows 0.45258)
                  l02: P(>=1 big) 0.32613  expected big seats 0.53610  entry pct 0.49326  |  QBs 10.21  distinct 41.3  dealt projection 129.25
  MIXT_THIRD      v2: P(>=1 big) 0.29499  expected big seats 0.47799  P(>=2) 0.12087  entry pct 0.48898  (live rows 0.51382, regulars' rows 0.44067)
                  l02: P(>=1 big) 0.31913  expected big seats 0.54105  entry pct 0.49690  |  QBs 8.85  distinct 38.1  dealt projection 129.41
  MIXT_TWOTHIRDS  v2: P(>=1 big) 0.29623  expected big seats 0.46415  P(>=2) 0.11466  entry pct 0.48720  (live rows 0.51803, regulars' rows 0.47134)
                  l02: P(>=1 big) 0.31970  expected big seats 0.51976  entry pct 0.49510  |  QBs 10.72  distinct 43.9  dealt projection 129.15
```

**Reading.**
1. **CONTRADICTS.** On 2022 the half book read −0.0227 [−0.0983, +0.0375] (P(≥ 1 big) 0.267 → 0.244). That is no
   difference at the rule, but the estimate is negative.
   - Every 2022 split read below the live book, on both fields.
   - Expected big seats fell by a tenth.
   - By the frozen go / no-go, the half book does not go into Week 5.
2. **Pooled over 2022–24 it is a wash:** +0.014 [−0.020, +0.046], expected big seats ratio 1.017. Study 46's +0.032
   was carried by 2023 (+0.043).
3. **What stays.**
   - The production switch stays off (`--mix-rs-rows` / `UNION_MIX_RS_ROWS` 0).
   - Study 38's amendment 5 is harmless at 0 (MIXT_QA0_FULL equals MIXT_QA0).
   - The real-field checks stay open: the laptop's Weeks 2–4 replay favoured the half book in all three weeks (a
     small sample), and study 38's paper arms track the regulars' structure on live FP weeks.
4. **The lesson for this harness.** Study 37 (the whole book) leaned worse, study 46 (half) leaned better on
   2023–24, and the half was level-to-worse on 2022. On our ratings the regulars' structure neither helps nor hurts
   P(≥ 1 big) by an amount these slates can see. The fair test is the live FP weeks (study 38).

## Addendum 151 (2026-10-06): study 47 (the QB-by-QB round-robin — each QB his best row in every shape): WORSE — about 5 points of weekly P(≥ 1 big) and 30% of the expected big seats lost; his round-robin over the shapes stays

**Setup.**
- **The question.** The operator queued the outside reviewer's wording (study list item 41): "for each QB in turn,
  build his best row under each shape". His live Week-5 fill is study 42's round-robin. It takes the SHAPES in turn
  and lets the solver pick the QB, so a top QB's 5 rows sit in about two shapes.
- **Arms.** The harness is study 46's: 36 slates, the calibrated field v2 decides, l02 beside it. Every arm uses the
  winners' quotas, the QB cap 5, caps 13 / 6, no term and the limit 4.
  - **MIXT_QBRR_ROW (DECISION).** The QBs go in order of their best A1 row. That row is solved on the empty state and
    rolled back, for the top 16 by projection. Each QB gets his best row in every shape that still has quota, with every
    other QB banned for that solve. Further passes run under the cap.
  - **MIXT_QBRR (exploratory):** the QBs in order of their own projection.
  - **Disclosed:** the census set the decision arm before the freeze, outcome-blind. The projection order also changes
    WHICH QBs fill the book (−1.85 against −0.64 per dealt lineup). The re-run census was byte-identical.
- **Preregistration:** `reports/2026-10-07-prereg-study47-qb-round-robin.md` (frozen `21d19345`, sha256 `b187cf7f…`).
- **Panel:** banks 1515–1520, B 20,000, seed 20261027.
- **The confirmatory census holds:** no QB at the 5-row cap (live 3.05), 3.25 shapes per QB (live 2.01), −0.62 per
  dealt lineup.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (diff empty, at lab
  `0f74949`; raw files equal to the RAW_MANIFEST).
  - Reader `6ba9898f`; READ `c8f01c96`.
  - The confirmatory census (`5254334`) was committed before the READ.
  - Lab: nfl2 `production/s47-qb-round-robin-20261006`; LEDGER row `4fbad6f`.

**Reader output (verbatim):**
```
STUDY 47 READER  sha256 6ba9898f364f9382da4de56e6ff27a8701efbfe6e1fc81a69bfa14291bbaa004
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1515, 1516, 1517, 1518, 1519, 1520]  B 20000  seed 20261027  primary MIXT_QBRR_ROW - MIXT_LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (QB order, row peek, live settings, QB cap, objective): [{"MIXT_LIVE": null, "MIXT_QBRR": "mean", "MIXT_QBRR_ROW": "row"}, 16, {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== MIXT_QBRR_ROW vs MIXT_LIVE  [DECISION: the QBs in turn (by their best row), each his best row in every cell; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate -0.05122  [-0.09955, -0.00403]  seasons 2023 -0.06138, 2024 -0.04106
  GUARD 1 mean entry pct -0.01154  one-sided lower -0.01924  (must exceed -0.015)
  GUARD 2 expected big seats 0.36731 vs 0.52003  ratio 0.706  (must be >= 0.80)
  MIXT_QBRR_ROW dealt identical to MIXT_LIVE: 0.000 of slate-banks
  ->  WORSE

== EXPLORATORY (never decision-bearing)
  MIXT_QBRR - MIXT_LIVE (QBs by their own projection): -0.03427  [-0.09700, +0.03040]  seasons 2023 -0.02402, 2024 -0.04452
  MIXT_QBRR_ROW - MIXT_LIVE (QBs by their best A1 row, the l02 field): -0.05261  [-0.10189, -0.00430]  seasons 2023 -0.06074, 2024 -0.04448
  MIXT_QBRR - MIXT_LIVE (QBs by their own projection, the l02 field): -0.03489  [-0.10319, +0.03441]  seasons 2023 -0.02160, 2024 -0.04819

the fields' lines (DK points, slate-bank means): v2 mean 128.10 p99 185.16 top-95 206.05  l02 mean 127.36 p99 183.68 top-95 204.57
secondaries (slate means; v2 = the calibrated field, l02 = studies 24-45's field):
  MIXT_LIVE     v2: P(>=1 big) 0.32508  expected big seats 0.52003  P(>=2) 0.12388  entry pct 0.51572
                l02: P(>=1 big) 0.35477  expected big seats 0.59273  entry pct 0.52410  |  QBs 8.14  cells per QB 2.01  distinct 31.4  dealt projection 128.59
  MIXT_QBRR     v2: P(>=1 big) 0.29081  expected big seats 0.39077  P(>=2) 0.07570  entry pct 0.48112
                l02: P(>=1 big) 0.31988  expected big seats 0.44539  entry pct 0.48929  |  QBs 8.02  cells per QB 3.24  distinct 40.3  dealt projection 126.66
  MIXT_QBRR_ROW v2: P(>=1 big) 0.27386  expected big seats 0.36731  P(>=2) 0.07454  entry pct 0.50418
                l02: P(>=1 big) 0.30216  expected big seats 0.41777  entry pct 0.51273  |  QBs 8.00  cells per QB 3.25  distinct 35.4  dealt projection 127.97
```

**Reading.**
1. **WORSE at the frozen rule.** P(≥ 1 big) fell −0.0512 [−0.0996, −0.0040] (0.325 → 0.274), negative in both
   seasons. Expected big seats fell by 29%, and the mean finish by about 1 point.
2. **Why.** Giving every top QB one row of each shape spends rows on shapes his game does not suit: a bring-back in a
   game without a shootout, or a lone receiver when his stack is the play. The round-robin over the shapes lets the
   solver put each shape on the QB it suits.
3. **With study 42** (value and round-robin level with the group fill), the fill question is closed. His round-robin
   stays, and no QB-major switch is built. Study list item 41: closed, WORSE.

## Addendum 152 (2026-10-06): study 48 (does a lineup "look like a winner"?): PASS — within his book, the rows that look more like recent winners score more than their projection says; the first choice among our own lineups that beats chance

**Setup.**
- **The operator (10-06 night):** "would there be any benefit to loading them into Neo4j and looking at each of them
  quickly and seeing if it looks like a winner?" Then: "I want to do it right away." On the inputs, through the outside
  reviewer's plan: every player's red-zone, touchdown and attempt facts.
- **The score.** A point-in-time ridge logistic model of "in the top 1% of a PRIOR slate's calibrated v2 field by
  realized points" against the rest. It is fitted on 2022 and the 2023–24 slates strictly before each scored slate,
  on 24 PRE-LOCK features:
  - **Shape and field:** the QB's WR / TE teammates, bring-back, QB-team RB, players from the QB's and the top-total
    game, salary used.
  - **Ownership:** the skill players' mean ownership rank. Training uses the prior slates' real ownership; scoring uses
    the pre-lock TABPFN prediction.
  - **Player history:** the players' prior top-1% frequency.
  - **The operator's per-player facts, aggregated over the lineup:**
    - red-zone and end-zone targets, goal-line carries;
    - target, carry, snap and route shares, WOPR, vacated share;
    - the QB's implied total, spread and game total;
    - lagged TDs over 4 / 8 games, and the QB's pass TDs and attempts over 4 (nflverse, strictly prior).
- **Disclosed:** the inputs were widened at the operator's request before the freeze, and the 2022–24 "winners" are
  sampled-field winners.
- **Preregistration:** `reports/2026-10-07-prereg-study48-winner-like.md` (frozen `3d890e34`, sha256 `ea1ff2ee…`). The
  training table is byte-deterministic (`66272167…`).
- **Panel:** his live book's 26 rows on each slate-bank; banks 1521–1526, B 20,000, seed 20261028.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to the
  RAW_MANIFEST; the prep and the binding census also reproduced).
  - Reader `c8d9ece7`; READ `477e0eea`.
  - The confirmatory census (`22c6530`) was committed before the READ (`4c30057`).
  - Lab: nfl2 `production/s48-winner-like-20261006`; LEDGER row `e5dee65`.

**Reader output (verbatim):**
```
STUDY 48 READER  sha256 c8d9ece7b3b4169b8d86492b58aa588c7ae7d71f3c3f947866ea7f1d7498cdb5
DIRECTION: POSITIVE = the more winner-like rows of a book finish better (at equal projection for the primary).
slates 36  banks [1521, 1522, 1523, 1524, 1525, 1526]  B 20000  seed 20261028  primary the partial rank correlation (score vs finish pct on the CALIBRATED field v2, projection held), two-sided 0.95; prep identity 66272167b80dc08b008060fa921f9cb67abecb2c12c8a17394b75d9670423ca1

== THE WINNER-LIKENESS SCORE on his live book  [DECISION]
  PRIMARY partial rank correlation (score vs finish, projection held) +0.08212  [+0.02884, +0.13449]  seasons 2023 +0.09503, 2024 +0.06921
  ->  PASS (looking like a winner predicts a better finish at equal projection; a candidate tiebreak, needing its own book-level test)

== EXPLORATORY (never decision-bearing)
  partial, the l02 field: +0.08212  [+0.02884, +0.13449]  seasons 2023 +0.09503, 2024 +0.06921
  plain rank correlation (no projection held), v2: +0.08821  [+0.03093, +0.14362]  seasons 2023 +0.09006, 2024 +0.08635
  top-5 minus bottom-5 rows by score: mean finish pct, v2: +0.06530  [+0.02167, +0.10801]  seasons 2023 +0.06887, 2024 +0.06174
  top-5 minus bottom-5 rows by score: top-1% rate, v2: +0.02130  [+0.00556, +0.04167]  seasons 2023 +0.01852, 2024 +0.02407

levels (slate means, v2): the 5 most winner-like rows' mean pct 0.5388, top-1% rate 0.0269; the 5 least: 0.4735, 0.0056
```

**Reading.**
1. **PASS.** The score's partial rank correlation with the realized finish at equal projection is +0.082
   [+0.029, +0.134], positive in both seasons. The five most winner-like rows of a book reach the top 1% 2.7% of the
   time; the five least, 0.6%.
   - The l02 line equals v2 by construction: a within-book rank statistic does not depend on which field converts the
     points.
2. **Leak check after the read:**
   - the frame's `*_l4` columns are 4-game means of the games BEFORE the week (correlation 0.986, against 0.953 when the
     week is included);
   - the weekly lags are strictly prior (tested);
   - the ownership rank at scoring is the pre-lock prediction;
   - the model and the history use earlier slates only.
3. **What it leans on.** The all-53 fit (`MODEL_all53.json`) weights:
   - **toward:** ownership rank (+0.20), snap share (+0.13), QB teammates (+0.11);
   - **against:** recent end-zone targets (−0.17) and touchdowns (−0.10), i.e. regression.
4. **By frozen §5 (PASS):** a use needs its own book-level test. That is study 48b: the same book dealt with the most
   winner-like rows on the big-entry ranks.
   - For Week 5 it also needs the production port by Friday 17:00 (`MODEL_all53` and `PORT_NOTES` on lab
     `production/s48-port-20261007`), parity, review, Friday's rehearsal and his yes.
   - **Transfer caveat:** this was measured under our projections, while his live book uses FP's.

## Addendum 153 (2026-10-07): study 48b (deal his book by the winner-likeness score): NO DIFFERENCE — re-dealing the book by the score does not raise P(≥ 1 big) and costs a tenth of the expected seats; not armed for Week 5

**Setup.**
- **The question.** Study 48 (Addendum 152) passed: within his book the more winner-like rows finish better at equal
  projection. Its frozen §5 asked for a book-level test of a use. The operator: "Test tonight, aim for Week 5".
- **The use, with no new lineups.** The SAME 26-row live book, built and scored exactly as in study 48, dealt three ways
  by production's head layout:
  - **DEAL_LIVE:** its own order (the entry-weighted shape interleave).
  - **DEAL_SCORE (DECISION):** positions by score, so the most winner-like rows land on the big-entry ranks 1–22 and the
    least on the $20-only ranks 23–26.
  - **DEAL_CELL (exploratory):** each position keeps its cell, and the rows within a cell go in score order.
- **Preregistration:** `reports/2026-10-07-prereg-study48b-winner-deal.md` (frozen `ed11d548`, sha256 `44af4f83…`).
- **Panel:** banks 1527–1532, B 20,000, seed 20261029.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to the
  RAW_MANIFEST).
  - Reader `604794cc`; READ `6d5f89c0`.
  - The confirmatory census (`b1950cc`) was committed before the READ (`d0d0150`).
  - LEDGER row lab `fb87aa5`.

**Reader output (verbatim):**
```
STUDY 48B READER  sha256 604794ccb8816f9526df9a8198b96456cf03951082829941b7a8a2d8715205e3
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1527, 1528, 1529, 1530, 1531, 1532]  B 20000  seed 20261029  primary DEAL_SCORE - DEAL_LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (deals, study 48's sha, its training table, live settings, QB cap, objective): [["DEAL_LIVE", "DEAL_SCORE", "DEAL_CELL"], "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "66272167b80dc08b008060fa921f9cb67abecb2c12c8a17394b75d9670423ca1", {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== DEAL_SCORE vs DEAL_LIVE  [DECISION: the same book, the most winner-like rows on the big ranks; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.00794  [-0.02970, +0.04391]  seasons 2023 +0.01846, 2024 -0.00258
  GUARD 1 mean entry pct -0.00244  one-sided lower -0.00766  (must exceed -0.015)
  GUARD 2 expected big seats 0.48590 vs 0.54053  ratio 0.899  (must be >= 0.80)
  DEAL_SCORE dealt identical to DEAL_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  DEAL_CELL - DEAL_LIVE (by the score within each cell): +0.02183  [-0.00327, +0.04841]  seasons 2023 +0.00996, 2024 +0.03371
  DEAL_SCORE - DEAL_LIVE (by the score, the l02 field): +0.00942  [-0.02847, +0.04571]  seasons 2023 +0.01532, 2024 +0.00352
  DEAL_CELL - DEAL_LIVE (by the score within each cell, the l02 field): +0.02073  [-0.00580, +0.04900]  seasons 2023 +0.01032, 2024 +0.03115

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field):
  DEAL_LIVE  v2: P(>=1 big) 0.30955  expected big seats 0.54053  P(>=2) 0.13291  entry pct 0.52096  |  mean score, ranks 1-22 -4.5181, ranks 23-26 -4.5070
             l02: P(>=1 big) 0.33883  expected big seats 0.61157  entry pct 0.52955
  DEAL_SCORE v2: P(>=1 big) 0.31749  expected big seats 0.48590  P(>=2) 0.11769  entry pct 0.51852  |  mean score, ranks 1-22 -4.4309, ranks 23-26 -4.9864
             l02: P(>=1 big) 0.34825  expected big seats 0.55556  entry pct 0.52709
  DEAL_CELL  v2: P(>=1 big) 0.33138  expected big seats 0.55028  P(>=2) 0.13380  entry pct 0.51919  |  mean score, ranks 1-22 -4.4646, ranks 23-26 -4.8010
             l02: P(>=1 big) 0.35957  expected big seats 0.61933  entry pct 0.52778
```

**Reading.**
1. **NO DIFFERENCE.** P(≥ 1 big) moved +0.008 [−0.030, +0.044]. Expected big seats fell by a tenth (ratio 0.899) and
   P(≥ 2) went from 0.133 to 0.118. Ordering the whole book by the score breaks the shape interleave that spreads the
   entries over the shapes.
2. **The within-cell order** (DEAL_CELL, exploratory) leans positive in both seasons: +0.022 [−0.003, +0.048], with
   expected big seats 0.550 against 0.541. It is the candidate for any further test.
3. **The real-field check.** The laptop's descriptive check of the score on the Week 3 and Week 4 replays, with
   production's port, found partial rank correlations of −0.10 and −0.02. That is no support, though 26 rows a week
   cannot contradict +0.08.
4. **Not armed for Week 5.**
   - Production's `--winner-order` is merged, reviewed and parity-pinned (0.0 against the private fixture), and it
     stays OFF.
   - Study 38 needs no amendment.
   - Next, his choice for Week 6 at the earliest: a confirmation of DEAL_CELL on fresh banks, and the weekly real-field
     line with the frozen model.

## Addendum 154 (2026-10-07): study 48d (choose his book by the winner-likeness score): NO DIFFERENCE, leaning positive in both seasons — about 2 points of P(≥ 1 big) at 1.7 projected points per row; not armed for Week 5

**Setup.**
- **The question.** Study 48 (Addendum 152) passed and study 48b (Addendum 153) showed re-dealing the same rows does not
  help. The operator asked "Why not adopt it?", and, offered the use that changes WHICH rows are entered: "Yes, test it
  now".
- **The use.** His live Week-5 book built with production's 15 spares: 41 rows through one state (the winners' mix,
  limit 4, round-robin, QB cap 5, caps 13 / 6, no term; study 48's module sha-asserted). All 41 are scored by the
  walk-forward model, then:
  - **LIVE:** rows 0–25, as today.
  - **SEL_CELL (DECISION):** per cell, its book count of the most winner-like of that cell's book rows and spares;
    build order within a cell, then the entry-weighted interleave.
  - **SEL_CELL_ORD (exploratory):** SEL_CELL with score order within each cell.
  - **SEL_ALL (exploratory):** the global top 26 of the 41.
  - Every chosen book stays within production's caps, QB cap and overlap limit (asserted on every slate-bank).
- **Preregistration:** `reports/2026-10-07-prereg-study48d-winner-select.md` (frozen `6d71534f`, sha256 `bffffe9b…`).
- **Panel:** banks 1533–1538, B 20,000, seed 20261030.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to the
  RAW_MANIFEST).
  - Reader `e786af21`; READ `8bdeb0b3`.
  - The confirmatory census (`00d24b8`, `3f3634fb`) was committed before the READ (`ea7e30c`).
  - LEDGER row lab `5421cfb`.

**Reader output (verbatim):**
```
STUDY 48D READER  sha256 e786af21fe541bf5ef651e2f68139d108b74d0a9fdf96429a00e4501f04b9c23
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1533, 1534, 1535, 1536, 1537, 1538]  B 20000  seed 20261030  primary SEL_CELL - LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (deals, study 48's sha, its training table, live settings, QB cap, objective): [["LIVE", "SEL_CELL", "SEL_CELL_ORD", "SEL_ALL"], "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "66272167b80dc08b008060fa921f9cb67abecb2c12c8a17394b75d9670423ca1", {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== SEL_CELL vs LIVE  [DECISION: per cell, the most winner-like of its book rows and spares; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.02090  [-0.01536, +0.06024]  seasons 2023 +0.02922, 2024 +0.01258
  GUARD 1 mean entry pct -0.01268  one-sided lower -0.02721  (must exceed -0.015)
  GUARD 2 expected big seats 0.53174 vs 0.51669  ratio 1.029  (must be >= 0.80)
  SEL_CELL dealt identical to LIVE: 0.014 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing)
  SEL_CELL_ORD - LIVE (per cell, score order within cells): +0.00957  [-0.03085, +0.05305]  seasons 2023 +0.03871, 2024 -0.01957
  SEL_ALL - LIVE (the global top 26): +0.02391  [-0.01468, +0.06335]  seasons 2023 +0.04061, 2024 +0.00721
  SEL_CELL - LIVE (per cell, the l02 field): +0.02190  [-0.01584, +0.06302]  seasons 2023 +0.02837, 2024 +0.01543
  SEL_CELL_ORD - LIVE (per cell, score order within cells, the l02 field): +0.01042  [-0.03160, +0.05646]  seasons 2023 +0.04037, 2024 -0.01954
  SEL_ALL - LIVE (the global top 26, the l02 field): +0.02235  [-0.01755, +0.06313]  seasons 2023 +0.03814, 2024 +0.00657

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field):
  LIVE         v2: P(>=1 big) 0.31945  expected big seats 0.51669  P(>=2) 0.11781  entry pct 0.51520  |  spares in 0.00  projection per row 128.09  score -4.5174
               l02: P(>=1 big) 0.34843  expected big seats 0.58883  entry pct 0.52368
  SEL_CELL     v2: P(>=1 big) 0.34035  expected big seats 0.53174  P(>=2) 0.12710  entry pct 0.50252  |  spares in 7.81  projection per row 126.37  score -4.3939
               l02: P(>=1 big) 0.37033  expected big seats 0.60143  entry pct 0.51095
  SEL_CELL_ORD v2: P(>=1 big) 0.32902  expected big seats 0.48629  P(>=2) 0.11114  entry pct 0.50033  |  spares in 7.81  projection per row 126.37  score -4.3939
               l02: P(>=1 big) 0.35885  expected big seats 0.55124  entry pct 0.50878
  SEL_ALL      v2: P(>=1 big) 0.34336  expected big seats 0.54746  P(>=2) 0.13837  entry pct 0.50163  |  spares in 8.11  projection per row 126.24  score -4.3714
               l02: P(>=1 big) 0.37079  expected big seats 0.61112  entry pct 0.51007
```

**Reading.**
1. **NO DIFFERENCE, leaning positive.** P(≥ 1 big) moved +0.021 [−0.015, +0.060], positive in both seasons (2023
   +0.029, 2024 +0.013). Expected big seats rose slightly (ratio 1.029) and P(≥ 2) went from 0.118 to 0.127.
2. **The price.** The chosen rows carry 1.7 fewer projected points each (126.37 against 128.09; 7.8 spares taken in),
   and the mean finish falls 1.3 percentile points (one-sided lower −0.027, past the −0.015 guard; the guards gate a
   PASS only). This is the same shape as study 46 (half and half): a bit more of the top, a bit less of the middle.
   The 2022 check of study 46 (46c) contradicted it.
3. **The exploratory arms agree in direction.** The global top 26 (SEL_ALL) +0.024 [−0.015, +0.063]; the l02 field
   +0.022. Score order within cells (SEL_CELL_ORD) +0.010, negative in 2024.
4. **Not armed for Week 5 by this read.**
   - Production's `--winner-select` stays OFF.
   - Any live use needs a 2022 check first (the 46c template). If he adopts it, study 38 needs an amendment before the
     lock.
   - Next: study 48e, his 10-07 request to apply the score at generation (every row must look winner-like before it
     enters the book).

## Addendum 155 (2026-10-07): study 48e (a winner-likeness gate at generation): NO DIFFERENCE on both co-primary decisions, leaning positive; the cheapest form of the idea, not armed

**Setup.**
- **The question.** The operator (10-07): "before a lineup is added to the corpus it needs to appear winner like ... I
  think that would be a good next test today". Studies 48b and 48d (Addenda 153–154) used study 48's score on rows
  already built; this gate acts while the book is built.
- **The arms.** His live Week-5 book and production's 15 spares (41 rows, one state: the winners' mix, round-robin, limit
  4, QB cap 5, caps 13 / 6, no term), built three ways:
  - **LIVE:** mix_fill's round-robin, called.
  - **GATE:** every peeked row is scored by study 48's walk-forward model. Below tau (the median score of the training
    top-1% rows of the prior slates), the row is banned for that peek and the cell re-solved, up to 10 tries; with no
    pass, the best try is committed (counted). The spares are gated too.
  - **GATE_SOFT:** the same with tau at the 25th percentile, the outside reviewer's "safer form".
- **Two co-primary decisions** (Bonferroni, each two-sided 0.975): the operator's rule when the agents disagree is to test
  both.
- **The real-field evidence, stated before the run:** the laptop's Week 2–4 whole-field check found no support for the
  score among high-projection lineups (AUC .49 / .54 / .39). So the prereg declared a harness PASS necessary, not
  sufficient: no Week-5 arming on any read, and study 48f (the real-field refit, graded prospectively) decides.
- **Production parity, done before the read:** the frozen live threshold −4.49767187489062 (`LIVE_TAU.json` `d1c8aaaa`;
  MODEL_all53, history 0); production's gate (`production/winner-gate-20261007` @ `7467b8ce`) reproduces the private
  fixture's 312 try scores and 41 picks.
- **Preregistration:** `reports/2026-10-07-prereg-study48e-winner-gate.md` (frozen `c636ef86`, sha256 `8370a8ca…`).
- **Panel:** banks 1539–1544, B 20,000, seed 20261031.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to the
  RAW_MANIFEST).
  - Reader `c4c92c18`; READ `81e7bd23`.
  - The confirmatory census (`b733e8c`, `a37c5e4d`) was committed before the READ (`3dd2be5`).
  - LEDGER row lab `3efd65a`.

**Reader output (verbatim):**
```
STUDY 48E READER  sha256 c4c92c18032da02281887cef2fe23a7bd788c953973f8bd7a415ad4b8a7e8f9b
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1539, 1540, 1541, 1542, 1543, 1544]  B 20000  seed 20261031  two co-primary decisions (GATE - LIVE, GATE_SOFT - LIVE) on the CALIBRATED field (v2), each two-sided 0.975 (Bonferroni), guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (definitions, R, study 48's sha, its training table, live settings, QB cap, objective): [{"GATE": 0.5, "GATE_SOFT": 0.25, "LIVE": null}, 10, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "66272167b80dc08b008060fa921f9cb67abecb2c12c8a17394b75d9670423ca1", {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== GATE vs LIVE  [DECISION (tau at the median of the training top-1% scores); every built row must look winner-like; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.01150  [-0.05456, +0.07576] (two-sided 0.975)  seasons 2023 +0.01022, 2024 +0.01279
  GUARD 1 mean entry pct +0.01019  one-sided lower -0.00032  (must exceed -0.015)
  GUARD 2 expected big seats 0.61101 vs 0.57371  ratio 1.065  (must be >= 0.80)
  GATE dealt identical to LIVE: 0.023 of slate-banks
  ->  NO DIFFERENCE

== GATE_SOFT vs LIVE  [DECISION (tau at the 25th percentile); every built row must look winner-like; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate +0.02065  [-0.04269, +0.08219] (two-sided 0.975)  seasons 2023 +0.01002, 2024 +0.03129
  GUARD 1 mean entry pct +0.00673  one-sided lower -0.00023  (must exceed -0.015)
  GUARD 2 expected big seats 0.59646 vs 0.57371  ratio 1.040  (must be >= 0.80)
  GATE_SOFT dealt identical to LIVE: 0.069 of slate-banks
  ->  NO DIFFERENCE

== STUDY: no decision passes: GATE NO DIFFERENCE; GATE_SOFT NO DIFFERENCE

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  GATE - LIVE (tau at the median, the l02 field): +0.00713  [-0.05275, +0.06482]  seasons 2023 +0.00268, 2024 +0.01159
  GATE_SOFT - LIVE (tau at the 25th percentile, the l02 field): +0.02034  [-0.03752, +0.07681]  seasons 2023 +0.00785, 2024 +0.03283

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  LIVE       v2: P(>=1 big) 0.33690  expected big seats 0.57371  P(>=2) 0.14106  entry pct 0.51139
             l02: P(>=1 big) 0.36619  expected big seats 0.64310  entry pct 0.51992
             book: gate pass rate nan  fallbacks nan  projection per row 128.11  score -4.5258  predicted ownership 78.26%  ownership rank 0.9379  salary 49968
  GATE       v2: P(>=1 big) 0.34840  expected big seats 0.61101  P(>=2) 0.15807  entry pct 0.52157
             l02: P(>=1 big) 0.37333  expected big seats 0.68276  entry pct 0.53024
             book: gate pass rate 0.754  fallbacks 6.39  projection per row 127.75  score -4.3520  predicted ownership 80.54%  ownership rank 0.9425  salary 49973
  GATE_SOFT  v2: P(>=1 big) 0.35755  expected big seats 0.59646  P(>=2) 0.14054  entry pct 0.51812
             l02: P(>=1 big) 0.38653  expected big seats 0.66595  entry pct 0.52661
             book: gate pass rate 0.949  fallbacks 1.33  projection per row 127.92  score -4.4214  predicted ownership 79.69%  ownership rank 0.9409  salary 49970
```

**Reading.**
1. **NO DIFFERENCE on both decisions, leaning positive in both seasons.** GATE +0.012 [−0.055, +0.076]; GATE_SOFT +0.021
   [−0.043, +0.082].
2. **The cheapest form of the winner-likeness idea in the harness.** The re-peeked rows cost little projection (−0.36 and
   −0.19 points per row, against −1.72 for 48d's selection). The mean finish did not fall (+0.010 and +0.007), and
   expected big seats rose slightly (ratios 1.065 and 1.040).
3. **The outside reviewer's re-chalk is real but small.** Predicted ownership rose 2.3 and 1.4 points per row, higher
   on 84% and 69% of slate-banks. The score's largest coefficient is the ownership rank.
4. **Not armed.**
   - By the frozen §5 the gate stays OFF. Production's `--winner-gate` (parity-pinned, not merged) stays unarmed.
   - The winner-likeness line now rests on study 48f: the score refit on the real 2026 fields, graded W5–W8 with the
     week as the unit.

## Addendum 156 (2026-10-07): study 49 (the prior-top term block in the harness): NO DIFFERENCE, leaning negative; the uncapped form costs a third of P(≥ 1 big)

**Setup.**
- **The question.** The operator put the prior-top term in Week 5 live, capped, on part of the book (10-07, "Live, capped,
  part of book").
  - The block: 8 of 26 rows built after the live block on the projection + min(0.20 × pred_own, 2.0).
  - pred_own: 5 × z within position of each player's mean share of the PRIOR weeks' real Millionaire top-1% lineups,
    clipped at 0.
  - Production: `union_reselect --term-block-rows 8`.
  - Its evidence was three in-sample weeks (the exact form: ahead in one of three).
  - He then said "Yes, run it" to this check: can the harness catch harm before Sunday?
- **The arms.** His live Week-5 book and production's 15 spares (41 rows, one state):
  - **LIVE:** mix_fill's round-robin, called.
  - **TERM8 (DECISION):** production's term block (`experiments/term_book.py` `62c2306e…`, the file study 38's amendment
    6 copies), with the block at ranks 2, 5, 9, 12, 15, 18, 22 and 25.
  - **TERM_ALL (exploratory):** every row on the uncapped term, the outside reviewer's replay form.
- **The harness analogue of the file:** each player's mean share of the season's prior slates' sampled top-1% lineups
  (the calibrated v2 field from each slate's REAL ownership, the top 1% by REALIZED points), 5 × z within position,
  clipped at 0. Week 1 has no file, so TERM8 equals LIVE on 2 of 36 slates.
- **Production parity:** study 38's amendment-6 smoke. The lab's book with the block equals the laptop's Week-4
  production union book, 26 of 26 positions.
- **Preregistration:** `reports/2026-10-07-prereg-study49-prior-top-block.md` (frozen `53bbb840`, sha256 `127f73e1…`).
- **Panel:** banks 1545–1550, B 20,000, seed 20261101.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to the
  RAW_MANIFEST).
  - Reader `8cae1f22`; READ `47cea4cc`.
  - The confirmatory census (`fba41f5`, `33cd67f0`) was committed before the READ (`84cfe8d`).
  - LEDGER row lab `95e98f7`.

**Reader output (verbatim):**
```
STUDY 49 READER  sha256 8cae1f22363637efa678a2125bd78dc5ca5e7e0796269d164337ef8e5ae9121f
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36  banks [1545, 1546, 1547, 1548, 1549, 1550]  B 20000  seed 20261101  primary TERM8 - LIVE on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (definitions, the term, study 48's sha, study 46's sha, the term block's sha, the training table, live settings, QB cap, objective): [["LIVE", "TERM8", "TERM_ALL"], {"cap": 2.0, "floor_proj": 5.0, "min_coverage": 0.5, "n_term": 8, "tilt": 0.2, "z_scale": 5.0}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "30647fef4175770e8f809cb704f282788f8b4d079319ba282768ad907433ec7a", "62c2306eff1135713d599b788bcbd29be9db308c2eb8537183f3d291b996b887", "66272167b80dc08b008060fa921f9cb67abecb2c12c8a17394b75d9670423ca1", {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]
the term block applied on 0.944 of slate-banks (Week 1 has no prior slate)

== TERM8 vs LIVE  [DECISION: production's prior-top term block, 8 rows, capped at 2 points; the calibrated field]
  PRIMARY P(>= 1 big seat) per slate -0.01651  [-0.07180, +0.05619]  seasons 2023 -0.02397, 2024 -0.00905
  GUARD 1 mean entry pct +0.00054  one-sided lower -0.00973  (must exceed -0.015)
  GUARD 2 expected big seats 0.53735 vs 0.56116  ratio 0.958  (must be >= 0.80)
  TERM8 dealt identical to LIVE: 0.056 of slate-banks
  ->  NO DIFFERENCE

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  TERM_ALL - LIVE (every row on the uncapped term): -0.11154  [-0.22059, +0.00396]  seasons 2023 -0.04095, 2024 -0.18212
  TERM8 - LIVE (the term block, the l02 field): -0.01565  [-0.07082, +0.05675]  seasons 2023 -0.02937, 2024 -0.00192
  TERM_ALL - LIVE (every row on the uncapped term, the l02 field): -0.11694  [-0.22727, +0.00047]  seasons 2023 -0.04483, 2024 -0.18905

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  LIVE      v2: P(>=1 big) 0.33231  expected big seats 0.56116  P(>=2) 0.14280  entry pct 0.51313
            l02: P(>=1 big) 0.35876  expected big seats 0.63814  entry pct 0.52162
            book: projection per row 128.16  predicted ownership 78.42%  capped term points per row 8.666
  TERM8     v2: P(>=1 big) 0.31580  expected big seats 0.53735  P(>=2) 0.14057  entry pct 0.51366
            l02: P(>=1 big) 0.34311  expected big seats 0.60451  entry pct 0.52212
            book: projection per row 127.69  predicted ownership 78.58%  capped term points per row 9.840
  TERM_ALL  v2: P(>=1 big) 0.22077  expected big seats 0.34002  P(>=2) 0.08278  entry pct 0.43960
            l02: P(>=1 big) 0.24182  expected big seats 0.37623  entry pct 0.44745
            book: projection per row 123.91  predicted ownership 72.58%  capped term points per row 12.217
```

**Reading.**
1. **NO DIFFERENCE, leaning negative in both seasons.** The capped 8-row block moved P(≥ 1 big) −0.017 [−0.072, +0.056]
   (0.332 → 0.316). Both guards held. It costs 0.48 projected points per row; its 8 rows project 123.9 against 129.2 for
   the live block's.
2. **The mechanism hurts at strength.** Riding the players in recent winning lineups, applied to every row uncapped,
   cost −0.112 [−0.221, +0.004] (0.332 → 0.221) and 7 points of mean finish. The cap and the 8-row limit are what keep
   the block near harmless.
3. **The caveat.** The harness's winners are sampled-field winners on real points. So this measures recent-hitter
   momentum in real outcomes, not the real field's ownership pattern.
4. **What follows.**
   - Not WORSE at the frozen rule, so by its §4 the block stays his Week-5 decision. The laptop takes him three options
     for Friday's arming: live 8 capped rows, paper only, or off.
   - Study 38's MIXT_QA0_NOTERM line measures the block on the real field every week it is live.

## Addendum 157 (2026-10-07): Addendum 8 corrected — the projection model never carried defense-vs-position (O-40)

**What Addendum 8 said.** Addendum 8 (2026-07-26) closed the head-to-head features. One sentence gave the reason:
"opponent info is already carried by trailing defense-vs-position form + the Vegas blend".

**What is true.** The production projection model (`models/featureset.py` `NUMERIC_FEATURES`) has NEVER contained a
defense-vs-position input.
- It carries game environment: implied team total, spread, game total, expected game script.
- It carries the opponent's pass coverage: `cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`, `db_ypt_allowed_l6`,
  `top_cb_out`.
- The position-level columns (`qb/rb/wr/te_fp_allowed_adj_l6`) and the defence EPA / red-zone columns are built into
  021 / 023 but were never registered as features (not in `NUMERIC_FEATURES` or `CANDIDATE_FEATURES`). No commit to
  `featureset.py` has ever added them (`git log -S fp_allowed_adj_l6`).
- They were also empty in the 2026 T-70 frames: W1–W3 0%, W4 91%. Today's serving join takes each defense's latest built
  row, one game stale. 0bc6b6bc (O-22, unmerged until after Week 5) serves them as-of by exact week.

**What still holds.** The head-to-head null result stands; only its stated reason was wrong. The "Vegas blend" part is
correct: the implied total and spread carry team-level defensive strength.

**What it measures.** A walk-forward SCREEN (2026-10-07; seen before any rule was frozen, so it decides nothing;
`reports/2026-10-07-prereg-o40-dvp-ablation.md` §1):
- Adding the four position columns changes the within-week rank correlation by +0.0005, +0.0021 and −0.0007 (2023,
  2024 and 2025), and MAE in the third decimal.
- On 2026 W2–W4 our residuals against in-season DvP flip sign (corr −0.12, −0.05, +0.13).
- So the missing input is real but, on this evidence, not costing the projections anything measurable.

**What decides.**
- The CONFIRMATORY ablation, frozen in that file's §2: the O-22-repaired base after the Monday merge, with untouched
  targets 2020–2022. A PASS buys only the projection-level gate.
- The consumer replay (2026 W2–W5): it decides the Week-6 question with the operator.
- Separately, by his decision (10-07), a paper arm: FP's means plus a walk-forward DvP correction (study 38 amendment 6c).

**Lesson.** A closing reason must be checked against the code, not stated from memory. Same class as "never cite an
addendum without checking for a correction". Verified for this correction: Addendum 8's sentence (as quoted), the
current `NUMERIC_FEATURES` list, `CANDIDATE_FEATURES`, the `featureset.py` history, and the screen table against the
O-40 record.

## Addendum 158 (2026-10-07): study 50 (the outside reviewer's factor bonuses in the harness): NO DIFFERENCE on both decisions; the whole-book matchup bonus leans negative on the read and positive on 2022

**Setup.**
- **The question.** The operator (10-07), on the outside reviewer's "why we missed the winners' players": "review this
  and schedule any necessary experiments this week". The reviewer's in-sample replay (Weeks 2–4) had the matchup and
  combined bonuses ahead in some weeks. Their weights were fixed before that replay but chosen on the same weeks.
- **The bonuses** (`make_factor_files.py`, ported verbatim):
  - **MATCHUP:** clip(1.0 × z, 0, 2), z within position of the opponent's DK points allowed to the position, a 6-game
    prior-season shrink.
  - **COMBINED_NOMKT:** clip(MATCHUP + the own-type vacated bonus clip(10 × share, 0, 3), 0, 3). The market part is
    excluded: there are no props in the history, and it is a dead lever under FP.
  - The points allowed come from nflverse weekly stats by the DK formula, point in time (tested).
- **The arms.** His live Week-5 book and production's 15 spares (41 rows, one state; mix_fill rr, limit 4, QB cap 5,
  caps 13 / 6), on player_mean (LIVE) and with each bonus on the objective.
- **Census** (outcome-blind, binding and confirmatory):
  - the bonuses cost 1.76 (MATCHUP) and 2.40 (COMBINED) projected points per row;
  - they rebuild almost the whole book (0.2 / 0.1 of 26 rows shared with LIVE);
  - the matchup bonus is independent of the harness projection (Spearman +0.004).
- **Rule.** Two co-primary decisions on the 2023–24 read (Bonferroni, two-sided 0.975 each) and a 2022 go / no-go per
  decision (point estimate < 0 = contradicted). ADOPTABLE = PASS and not contradicted.
- **Preregistration:** `reports/2026-10-08-prereg-study50-factor-bonuses.md` (frozen `f96067d3`, sha256 `8976e320…`).
- **Panel:** banks 1551–1556, B 20,000, seed 20261102. The run was 10-07, a day before the plan, because the machine was
  free.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to
  `RAW_s50_run.sha256`).
  - Reader `76366b13`; READ `781e06f9`.
  - The confirmatory census (`da62bd4`, `aacc85e5`) was committed before the READ (`e123c7f`).
  - LEDGER row lab `b4df5d0`.

**Reader output (verbatim):**
```
STUDY 50 READER  sha256 76366b131f7223890b1442f80d5e70050a7e259f7144cbc2557db45d543acb16
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1551, 1552, 1553, 1554, 1555, 1556]  B 20000  seed 20261102  two co-primary decisions (MATCHUP - LIVE, COMBINED_NOMKT - LIVE) on the CALIBRATED field (v2), each two-sided 0.975 (Bonferroni), guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval)
arms (definitions, the bonus constants, study 48's sha, live settings, QB cap, objective): [["LIVE", "MATCHUP", "COMBINED_NOMKT"], {"clip_combined": 3.0, "clip_matchup": 2.0, "clip_vacated": 3.0, "prior_games": 6.0, "w_matchup": 1.0, "w_vacated": 10.0}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", {"fill": "rr", "max_shared": 4}, 5, "player_mean (+ the arm's bonus)"]

== MATCHUP vs LIVE  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.07374  [-0.15997, +0.01073] (two-sided 0.975)  seasons 2023 -0.03869, 2024 -0.10879
  GUARD 1 mean entry pct -0.00410  one-sided lower -0.02839  (must exceed -0.015)
  GUARD 2 expected big seats 0.45579 vs 0.60301  ratio 0.756  (must be >= 0.80)
  MATCHUP dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.09449  [-0.02778, +0.22029] (two-sided 0.95)  ->  not contradicted

== COMBINED_NOMKT vs LIVE  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.02605  [-0.12490, +0.07474] (two-sided 0.975)  seasons 2023 +0.01431, 2024 -0.06641
  GUARD 1 mean entry pct +0.00150  one-sided lower -0.02917  (must exceed -0.015)
  GUARD 2 expected big seats 0.63329 vs 0.60301  ratio 1.050  (must be >= 0.80)
  COMBINED_NOMKT dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.06165  [-0.05902, +0.19333] (two-sided 0.95)  ->  not contradicted

== STUDY: no decision adoptable: MATCHUP NO DIFFERENCE on 2023-24, not contradicted on 2022; COMBINED_NOMKT NO DIFFERENCE on 2023-24, not contradicted on 2022

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  MATCHUP - LIVE (the l02 field, 2023-24): -0.07862  [-0.15627, -0.00226]  seasons 2023 -0.04320, 2024 -0.11404
  MATCHUP - LIVE (the l02 field, 2022): +0.10548  [-0.01159, +0.22766]  seasons 2022 +0.10548
  COMBINED_NOMKT - LIVE (the l02 field, 2023-24): -0.03441  [-0.11942, +0.05242]  seasons 2023 +0.00401, 2024 -0.07283
  COMBINED_NOMKT - LIVE (the l02 field, 2022): +0.06698  [-0.05908, +0.20378]  seasons 2022 +0.06698

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2023-24]
  LIVE            v2: P(>=1 big) 0.34641  expected big seats 0.60301  P(>=2) 0.15002  entry pct 0.51836  |  l02: P(>=1 big) 0.37418
                  book: projection per row 128.13  predicted ownership 78.24%  matchup points per row 3.897  combined points per row 7.006
  MATCHUP         v2: P(>=1 big) 0.27268  expected big seats 0.45579  P(>=2) 0.10705  entry pct 0.51426  |  l02: P(>=1 big) 0.29556
                  book: projection per row 126.37  predicted ownership 78.74%  matchup points per row 7.406  combined points per row 10.007
  COMBINED_NOMKT  v2: P(>=1 big) 0.32037  expected big seats 0.63329  P(>=2) 0.15810  entry pct 0.51986  |  l02: P(>=1 big) 0.33977
                  book: projection per row 125.73  predicted ownership 76.32%  matchup points per row 6.385  combined points per row 12.340
  [2022]
  LIVE            v2: P(>=1 big) 0.19730  expected big seats 0.32584  P(>=2) 0.08659  entry pct 0.45076  |  l02: P(>=1 big) 0.21119
                  book: projection per row 132.23  predicted ownership nan%  matchup points per row 3.650  combined points per row 6.548
  MATCHUP         v2: P(>=1 big) 0.29178  expected big seats 0.41130  P(>=2) 0.09052  entry pct 0.47974  |  l02: P(>=1 big) 0.31668
                  book: projection per row 130.40  predicted ownership nan%  matchup points per row 7.423  combined points per row 9.914
  COMBINED_NOMKT  v2: P(>=1 big) 0.25894  expected big seats 0.34017  P(>=2) 0.06823  entry pct 0.46172  |  l02: P(>=1 big) 0.27817
                  book: projection per row 129.62  predicted ownership nan%  matchup points per row 6.337  combined points per row 12.422
```

**Reading.**
- **Neither decision is adoptable.** Both read NO DIFFERENCE, and neither is contradicted on 2022.
- **The whole-book matchup bonus leans NEGATIVE on the read.**
  - About −7 points of P(≥ 1 big) (0.346 → 0.273), worse in 2024 (−0.109) than in 2023 (−0.039).
  - It keeps 0.756 of the expected big seats, past his 20% tolerance; both guards would fail.
  - On the earlier l02 field the exploratory interval excludes 0.
  - 2022 leans the other way: +0.094, interval through 0.
  - The seasons disagree, so there is no evidence of a gain. If anything there is mild evidence of harm in the two read
    seasons.
- **The combined form is flat:** −0.026, ratio 1.05.
- **It is consistent with:**
  - the outside reviewer's own out-of-sample note (odds ratio 1.07 per sd in 2023–25, nothing in 2026 Weeks 1–4);
  - O-40's screen (matchup columns add about 0 to the projection model);
  - the census: a bonus independent of the projection, bought with about 1.8 projected points per row.

**What it means.**
- The bonuses stay OFF as whole-book rules.
- Study 38's paper arms (MIXT_QA0_MATCHUPX, MIXT_QA0_COMBINED; amendment 6d, read against NOTERM since 6e) keep the
  weekly real-field record, which is the reviewer's in-sample replay checked out of sample.
- **The operator's 8-row matchup BLOCK** (his 10-07 request; production `matchup_block_file.py`) is decided by study
  51's frozen Saturday rule on its own banks. Study 51's design and stop rule were committed (`472434c7`, lab `93e0810`)
  BEFORE this read: the same slates, so the rule could not be tuned to this result.

## Addendum 159 (2026-10-07): study 51 (the matchup bonus as the live 8-row capped block): NO DIFFERENCE; by its frozen Saturday rule ENTERABLE at his decision

**Setup.**
- **The question.** The operator (10-07): "Please try to tackle the 'matchup bonus' one this week". He wants the outside
  reviewer's matchup bonus LIVE in his Week-5 book as a capped block like the prior-top one: production's
  `union_reselect --term-block-rows 8` on `scripts/matchup_block_file.py`'s file (every skill player, pred_own =
  b_matchup / 0.20, tilt 0.20, cap 2.0). His decision is at Saturday's arming, after the tests.
- **The arms.** His live Week-5 book and production's 15 spares (41 rows, one state), built two ways:
  - **LIVE:** study 48d's rows.
  - **MBLOCK8:** production's term block (`term_book.py` `62c2306e`), with study 50's MATCHUP as the term through
    production's own_bonus and the cap; the block at ranks 2, 5, 9, 12, 15, 18, 22 and 25.
- **Census:** −0.70 projected points per row; 16.2 of 26 rows shared with LIVE; the block's rows project 123.4 with 8.9
  term points each.
- **The frozen Saturday rule.** It was committed in the DRAFT (`472434c7`) BEFORE study 50's read, on the same slates.
  - NOT ENTERED if the read is WORSE, or 2022 is CONTRADICTED, or the expected-big-seats ratio is < 0.80 (his
    tolerance).
  - MOOT on a dead lever.
  - Otherwise ENTERABLE, his decision.
- **Preregistration:** `reports/2026-10-08-prereg-study51-matchup-block.md` (frozen `56674479`, sha256 `1dfac1a9…`).
- **Panel:** banks 1557–1562, B 20,000, seed 20261103.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop** (raw files equal to
  `RAW_s51_run.sha256`).
  - Reader `2cba7163`; READ `b605304f`.
  - The confirmatory census (`e357df4`, `256b14ac`) was committed before the READ (`3b150a8`).
  - LEDGER row lab `84c54db` (order 49 / 50 / 51 merged, `592f015`).

**Reader output (verbatim):**
```
STUDY 51 READER  sha256 2cba71638ed1ba9e0faa64ef1fb629f7a42176adcb674279bd19cdad8295df63
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1557, 1558, 1559, 1560, 1561, 1562]  B 20000  seed 20261103  one decision (MBLOCK8 - LIVE) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval)
arms (definitions, the term, study 48's sha, study 50's sha, the term block's sha, live settings, QB cap, objective): [["LIVE", "MBLOCK8"], {"bonus": "study 50 MATCHUP", "cap": 2.0, "floor_proj": 5.0, "min_coverage": 0.5, "n_term": 8, "tilt": 0.2}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "bf4704a0d94ad87938fc29bf94d20fc9deb86f857f454e671f5cd195c1e74265", "62c2306eff1135713d599b788bcbd29be9db308c2eb8537183f3d291b996b887", {"fill": "rr", "max_shared": 4}, 5, "player_mean (+ the block's capped term)"]
the block applied on 1.000 of slate-banks

== MBLOCK8 vs LIVE  [DECISION: the matchup bonus as production's 8-row capped block; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate +0.01272  [-0.02993, +0.05417] (two-sided 0.95)  seasons 2023 +0.05214, 2024 -0.02670
  GUARD 1 mean entry pct -0.00332  one-sided lower -0.01372  (must exceed -0.015)
  GUARD 2 expected big seats 0.54474 vs 0.58624  ratio 0.929  (must be >= 0.80)
  MBLOCK8 dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.02339  [-0.02532, +0.08571] (two-sided 0.95)  ->  not contradicted

== SATURDAY (the frozen rule for Week 5's live block): ENTERABLE, his decision: no harm shown and no gain shown (NO DIFFERENCE on the read, not contradicted on 2022)

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  MBLOCK8 - LIVE (the l02 field, 2023-24): +0.00977  [-0.03347, +0.05179]  seasons 2023 +0.05017, 2024 -0.03063
  MBLOCK8 - LIVE (the l02 field, 2022): +0.02617  [-0.02548, +0.09094]  seasons 2022 +0.02617

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2023-24]
  LIVE     v2: P(>=1 big) 0.32936  expected big seats 0.58624  P(>=2) 0.14268  entry pct 0.51773  |  l02: P(>=1 big) 0.36122
           book: projection per row 128.14  predicted ownership 78.48%  term points per row 3.912
  MBLOCK8  v2: P(>=1 big) 0.34208  expected big seats 0.54474  P(>=2) 0.12626  entry pct 0.51441  |  l02: P(>=1 big) 0.37099
           book: projection per row 127.43  predicted ownership 78.85%  term points per row 5.479
  [2022]
  LIVE     v2: P(>=1 big) 0.21820  expected big seats 0.30217  P(>=2) 0.06776  entry pct 0.44102  |  l02: P(>=1 big) 0.23163
           book: projection per row 132.21  predicted ownership nan%  term points per row 3.687
  MBLOCK8  v2: P(>=1 big) 0.24160  expected big seats 0.31343  P(>=2) 0.05995  entry pct 0.45046  |  l02: P(>=1 big) 0.25780
           book: projection per row 131.51  predicted ownership nan%  term points per row 5.332
```

**Reading.**
- **Neither harm nor gain is shown.** The 8-row block leans slightly positive:
  - +1.3 points of P(≥ 1 big) on 2023–24 (2023 +5.2, 2024 −2.7);
  - +2.3 on 2022;
  - about 7% fewer expected big seats, inside his tolerance.
- None of the frozen stop conditions holds, so **the block is enterable at his call**.
- **The whole-book form leaned negative (study 50, −7.4 points; ratio 0.756).** Diluting the bonus to 8 rows is what
  keeps it harmless. It is a small bet, not a supported gain.

**Beside it, the laptop's in-sample Week 2–4 replays** (production writers, Saturday 10:00 CT props cut; frozen harm
screens `f61aa4cc` / `28e28ab9`, committed before any number):
- **MBLOCK8:** P(≥ 1 big) .031 / .018 / .530 vs LIVE .041 / .002 / .434. Ahead in 2 of 3 weeks; pooled ratio 1.40.
- **The operator's TD-value block (TDBLOCK8):** NOT ENTERED by its screen (below LIVE in Weeks 2 and 4).
- **The combined matchup + TD block:** passes its screen only in-sample, carried by Week 4 alone. Its TD half failed on
  its own.
- **The TD re-deal:** NOT ENTERED (below LIVE in all three weeks; ratio 0.101). Study 52 tests the deal out of sample.

**What it means.**
- **For Saturday's block slot, the matchup block is the only option with out-of-sample support**, and that support is
  "not harmful", not "better".
- If he enters it, study 38's line "QA0 − NOTERM (the live block: matchup-w5.csv)" (amendment 6e) records it on the
  real field from Week 5.
- If he does not, the bonus stays on paper through study 38's whole-book arms.

## Addendum 160 (2026-10-07): study 52 (deal the book by the lineups' projected touchdowns): NO DIFFERENCE, NOT SUPPORTED; with the in-sample market re-deal NOT ENTERED, the idea is closed

**Setup.**
- **The question.** The operator (10-07): "if we haven't already, I'd like to try sorting our lineups by projected
  touchdowns for the lineup". It had not been tried before. The nearest is study 48b's re-deal by a winner-likeness
  score (Addendum 153, NO DIFFERENCE).
- **The arms.** The SAME 41 rows (his live book + 15 spares, study 48d's build), dealt three ways by production's head
  layout:
  - **DEAL_LIVE:** the book's own order.
  - **DEAL_TD** (the decision): positions by the lineup's projected touchdowns, most first, so the most-TD rows take the
    big-entry ranks 1–22 and the Millionaire's 1–2.
  - **DEAL_PROJ** (a control): positions by projection.
- **The touchdowns.**
  - They come from the hierarchical simulator's pre-lock worlds, already drawn for player_mean (`simulate_hsim`'s
    additive capture; the draws are unchanged, asserted in the smoke).
  - Per player: the mean rushing + receiving TDs. Passing is excluded, because production's input would be the market's
    anytime-TD price.
  - They are summed over the lineup.
- **Census:**
  - DEAL_TD moves 24.6 of 26 rows;
  - the Millionaire's positions carry 4.48 projected TDs vs 4.08, at equal projection;
  - a row's TDs correlate +0.40 with its projection.
- **Rule.** One decision on the 2023–24 read (two-sided 0.95, the usual guards) and the 2022 go / no-go. SUPPORTED only
  if PASS and not contradicted.
- **Preregistration:** `reports/2026-10-08-prereg-study52-td-deal.md`.
  - The DRAFT (`3641979b`) came before study 51's read and before the laptop's re-deal numbers.
  - Frozen `499b2257`, sha256 `4ef7195c…`.
- **Panel:** banks 1563–1568, B 20,000, seed 20261104.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop**.
  - Reader `040794f1`; READ `dd505310`; census `caeae9ff`; LEDGER row lab `6e13d84`.
  - The confirmatory census was committed (`504e153`, 10:15:27 CT) before the READ was written (10:15:33).
  - GitHub refused every push from about 10:09 CT, so both commits landed at 10:17.

**Reader output (verbatim):**
```
STUDY 52 READER  sha256 040794f1a1d8a0b99d2cb11bc90c1edb0f2a08a62f27002c59b04bf828f52a5f
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1563, 1564, 1565, 1566, 1567, 1568]  B 20000  seed 20261104  one decision (DEAL_TD - DEAL_LIVE) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval)
arms (definitions, the touchdown projection, study 48's sha, live settings, QB cap, objective): [["DEAL_LIVE", "DEAL_TD", "DEAL_PROJ"], "the simulator's mean rushing + receiving touchdowns per player (passing excluded)", "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", {"fill": "rr", "max_shared": 4}, 5, "player_mean (no ownership term)"]

== DEAL_TD vs DEAL_LIVE  [DECISION: the same book dealt by the lineups' projected touchdowns; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.02207  [-0.05925, +0.01408] (two-sided 0.95)  seasons 2023 -0.02550, 2024 -0.01863
  GUARD 1 mean entry pct -0.00060  one-sided lower -0.00549  (must exceed -0.015)
  GUARD 2 expected big seats 0.49353 vs 0.55809  ratio 0.884  (must be >= 0.80)
  DEAL_TD dealt identical to DEAL_LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.01957  [-0.02835, +0.06945] (two-sided 0.95)  ->  not contradicted

== STUDY: NOT SUPPORTED: NO DIFFERENCE on the 2023-24 read, not contradicted on 2022

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  DEAL_PROJ - DEAL_LIVE (the projection-order control), 2023-24: -0.01557  [-0.04845, +0.01642]  seasons 2023 -0.01193, 2024 -0.01921
  DEAL_PROJ - DEAL_LIVE (the projection-order control), 2022: +0.00084  [-0.04321, +0.04565]  seasons 2022 +0.00084
  DEAL_TD - DEAL_PROJ (the touchdowns beyond the projection), 2023-24: -0.00650  [-0.03213, +0.01897]  seasons 2023 -0.01357, 2024 +0.00058
  DEAL_TD - DEAL_PROJ (the touchdowns beyond the projection), 2022: +0.01873  [-0.02590, +0.06668]  seasons 2022 +0.01873
  DEAL_TD - DEAL_LIVE (the l02 field, 2023-24): -0.02092  [-0.05969, +0.01618]  seasons 2023 -0.02669, 2024 -0.01515
  DEAL_TD - DEAL_LIVE (the l02 field, 2022): +0.01830  [-0.02943, +0.06765]  seasons 2022 +0.01830
  the mechanism (2023-24, slate-banks 216): top-1% share of each book's 5 most-TD rows 0.0157 vs its 5 fewest-TD rows 0.0120

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the deals are pre-lock facts):
  [2023-24]
  DEAL_LIVE v2: P(>=1 big) 0.33824  expected big seats 0.55809  P(>=2) 0.13109  entry pct 0.51798  |  l02: P(>=1 big) 0.36754  |  projected TDs on positions 1-22 3.945
  DEAL_TD   v2: P(>=1 big) 0.31617  expected big seats 0.49353  P(>=2) 0.10995  entry pct 0.51738  |  l02: P(>=1 big) 0.34662  |  projected TDs on positions 1-22 3.997
  DEAL_PROJ v2: P(>=1 big) 0.32267  expected big seats 0.51819  P(>=2) 0.13005  entry pct 0.51854  |  l02: P(>=1 big) 0.35316  |  projected TDs on positions 1-22 3.952
  [2022]
  DEAL_LIVE v2: P(>=1 big) 0.25688  expected big seats 0.35190  P(>=2) 0.07322  entry pct 0.44986  |  l02: P(>=1 big) 0.27577  |  projected TDs on positions 1-22 3.908
  DEAL_TD   v2: P(>=1 big) 0.27645  expected big seats 0.44797  P(>=2) 0.11242  entry pct 0.45099  |  l02: P(>=1 big) 0.29407  |  projected TDs on positions 1-22 3.962
  DEAL_PROJ v2: P(>=1 big) 0.25772  expected big seats 0.36861  P(>=2) 0.08506  entry pct 0.45014  |  l02: P(>=1 big) 0.27645  |  projected TDs on positions 1-22 3.920
```

**Reading.**
- **Dealing by projected touchdowns does not raise the big-win chance.** It leans slightly negative in both read
  seasons (−2.2 points; 2023 −2.6, 2024 −1.9), with 12% fewer expected big seats.
- **The touchdowns add nothing beyond the projection** (DEAL_TD − DEAL_PROJ −0.0065).
- **The book's own order beats both re-sorts.**
- At the row level, a book's 5 most-TD rows hit the top 1% slightly more often (1.57% vs 1.20%). The deal does not
  convert that into seats, because a re-deal only moves rows between contests.

**Beside it:** the laptop's in-sample Week 2–4 re-deal by the market's summed anytime-TD probability (its frozen harm
screen `28e28ab9`) read NOT ENTERED. It was below LIVE in all three weeks, ratio 0.101, carried by Week 4's single hit.

**What it means.** The idea was tested on both inputs, the market's TD prices in-sample and the simulator's TDs out of
sample, and neither helps. It is closed unless a new TD source appears. The outside reviewer's real-field screen of sort
keys points the same way (`b335d1fd`: the TD key improves the average finish, and is level with random picks at the
top).

## Addendum 161 (2026-10-07): study 53 (a soft preference for sub-$4,000 players): no whole-book decision adoptable; neither 8-row block enterable for Week 5 (the +2 block a knife edge, stopped by the frozen 2022 rule)

**Setup.**
- **The question.** The outside reviewer's graph finding (relayed at the operator's request): within the regulars' own
  Week 1–4 portfolios, top-1% lineups carried more sub-$4,000 non-DST players (+0.43 sd).
  - Their in-sample Week 2–4 replays were dose-unstable as a whole-book bonus, and ahead of LIVE in all three weeks as an
    8-row block.
  - Addendum 77 had deleted the HARD punt mandate with no effect; a SOFT preference was never tested.
- **The arms.** His live Week-5 book and production's 15 spares (41 rows, one state; study 48d's LIVE):
  - **CHEAP2 / CHEAP4** (whole book, the decisions): +2 / +4 projected points per non-DST player salaried under $4,000
    (WR / TE at DK's floors).
  - **CHEAP2_BLOCK8 / CHEAP4_BLOCK8** (amendment 1, before any scored bank): the same terms as production's 8-row block
    (cap = the dose), under study 51's frozen SATURDAY rule.
- **Support census:** on 2023–24, sub-$4k players per row LIVE 1.09, CHEAP2 2.32, CHEAP4 2.97, the blocks 1.59 / 1.77.
  Projection per row −1.19 / −3.05 / −0.43 / −0.93. Amendment 1 left the four frozen arms identical on all 53 slates.
- **The operator's stated leaning** (relayed): the cheap block at +2 "if study 53's block read doesn't contradict it".
- **Preregistration:** `reports/2026-10-08-prereg-study53-cheap-pref.md` (frozen `000601cc`; amendment 1 `9ad836fe`,
  sha256 `de2c5181…`).
- **Panel:** banks 1569–1574, B 20,000, seed 20261105.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop**.
  - Reader `0d241d83`; READ `f587bb8c`; census `384ac944`.
  - The confirmatory census (`d611a9d`) was committed before the READ (`fd9687d`).
  - LEDGER row lab `5e0c9ce` (plus the closed prop-ladder row, `18ea688`).

**Reader output (verbatim):**
```
STUDY 53 READER  sha256 0d241d8314452ca13dfe49a1ab40c915636533de5b9f14720f41e38f762acc6e
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1569, 1570, 1571, 1572, 1573, 1574]  B 20000  seed 20261105  two co-primary decisions (CHEAP2 - LIVE, CHEAP4 - LIVE) on the CALIBRATED field (v2), each two-sided 0.975 (Bonferroni), guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval)
arms (definitions, the cheap constants, study 48's sha, the term block's sha, live settings, QB cap, objective): [["LIVE", "CHEAP2", "CHEAP4", "CHEAP4_BLOCK8", "CHEAP2_BLOCK8"], {"block": {"caps": {"CHEAP2_BLOCK8": 2.0, "CHEAP4_BLOCK8": 4.0}, "floor_proj": 5.0, "min_coverage": 0.5, "n_term": 8, "tilt": 0.2}, "doses": {"CHEAP2": 2.0, "CHEAP4": 4.0}, "salary_below": 4000}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "62c2306eff1135713d599b788bcbd29be9db308c2eb8537183f3d291b996b887", {"fill": "rr", "max_shared": 4}, 5, "player_mean (+ the arm's cheap-player bonus)"]

== CHEAP2 vs LIVE  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.01196  [-0.07657, +0.05424] (two-sided 0.975)  seasons 2023 +0.02464, 2024 -0.04856
  GUARD 1 mean entry pct -0.01378  one-sided lower -0.03536  (must exceed -0.015)
  GUARD 2 expected big seats 0.47644 vs 0.53415  ratio 0.892  (must be >= 0.80)
  CHEAP2 dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.01375  [-0.09658, +0.11887] (two-sided 0.95)  ->  not contradicted

== CHEAP4 vs LIVE  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.08774  [-0.19395, +0.02179] (two-sided 0.975)  seasons 2023 -0.07333, 2024 -0.10215
  GUARD 1 mean entry pct -0.04106  one-sided lower -0.07588  (must exceed -0.015)
  GUARD 2 expected big seats 0.35508 vs 0.53415  ratio 0.665  (must be >= 0.80)
  CHEAP4 dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: -0.00297  [-0.13974, +0.13014] (two-sided 0.95)  ->  CONTRADICTED (the 2022 point estimate is < 0)

== STUDY: no decision adoptable: CHEAP2 NO DIFFERENCE on 2023-24, not contradicted on 2022; CHEAP4 NO DIFFERENCE on 2023-24, CONTRADICTED (the 2022 point estimate is < 0) on 2022

== CHEAP2_BLOCK8 vs LIVE  [SATURDAY (amendment 1): the block form for Week 5's one block slot; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate +0.00413  [-0.03070, +0.04265] (two-sided 0.95)  seasons 2023 +0.02127, 2024 -0.01302
  GUARD 1 mean entry pct -0.00195  one-sided lower -0.01228  (must exceed -0.015)
  GUARD 2 expected big seats 0.50013 vs 0.53415  ratio 0.936  (must be >= 0.80)
  CHEAP2_BLOCK8 dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: -0.00163  [-0.05378, +0.05076] (two-sided 0.95)  ->  CONTRADICTED (the 2022 point estimate is < 0)
  SATURDAY: NOT ENTERED: CONTRADICTED on 2022

== CHEAP4_BLOCK8 vs LIVE  [SATURDAY (amendment 1): the block form for Week 5's one block slot; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate -0.01363  [-0.04908, +0.02210] (two-sided 0.95)  seasons 2023 -0.01665, 2024 -0.01062
  GUARD 1 mean entry pct -0.01018  one-sided lower -0.02312  (must exceed -0.015)
  GUARD 2 expected big seats 0.47474 vs 0.53415  ratio 0.889  (must be >= 0.80)
  CHEAP4_BLOCK8 dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: -0.00138  [-0.05463, +0.05406] (two-sided 0.95)  ->  CONTRADICTED (the 2022 point estimate is < 0)
  SATURDAY: NOT ENTERED: CONTRADICTED on 2022

== SATURDAY (the block slot): neither block dose is enterable

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  CHEAP2_BLOCK8 - LIVE (the l02 field, 2023-24): +0.00550  [-0.03064, +0.04513]  seasons 2023 +0.02235, 2024 -0.01136
  CHEAP2_BLOCK8 - LIVE (the l02 field, 2022): +0.00189  [-0.05283, +0.05735]  seasons 2022 +0.00189
  CHEAP4_BLOCK8 - LIVE (the l02 field, 2023-24): -0.01477  [-0.05190, +0.02252]  seasons 2023 -0.02056, 2024 -0.00897
  CHEAP4_BLOCK8 - LIVE (the l02 field, 2022): +0.00222  [-0.05350, +0.06016]  seasons 2022 +0.00222
  CHEAP2 - LIVE (the l02 field, 2023-24): -0.01786  [-0.07492, +0.03965]  seasons 2023 +0.01347, 2024 -0.04919
  CHEAP2 - LIVE (the l02 field, 2022): +0.01827  [-0.09752, +0.12956]  seasons 2022 +0.01827
  CHEAP4 - LIVE (the l02 field, 2023-24): -0.09134  [-0.18524, +0.00673]  seasons 2023 -0.08247, 2024 -0.10022
  CHEAP4 - LIVE (the l02 field, 2022): +0.00087  [-0.14212, +0.13916]  seasons 2022 +0.00087

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2023-24]
  LIVE            v2: P(>=1 big) 0.32685  expected big seats 0.53415  P(>=2) 0.12507  entry pct 0.51515  |  l02: P(>=1 big) 0.35737
                  book: projection per row 128.14  salary 49970  predicted ownership 78.18%  cheap players per row 1.09
  CHEAP2          v2: P(>=1 big) 0.31490  expected big seats 0.47644  P(>=2) 0.11078  entry pct 0.50137  |  l02: P(>=1 big) 0.33951
                  book: projection per row 126.96  salary 49954  predicted ownership 73.54%  cheap players per row 2.32
  CHEAP4          v2: P(>=1 big) 0.23912  expected big seats 0.35508  P(>=2) 0.08254  entry pct 0.47408  |  l02: P(>=1 big) 0.26603
                  book: projection per row 125.10  salary 49922  predicted ownership 69.02%  cheap players per row 2.97
  CHEAP4_BLOCK8   v2: P(>=1 big) 0.31322  expected big seats 0.47474  P(>=2) 0.11034  entry pct 0.50496  |  l02: P(>=1 big) 0.34260
                  book: projection per row 127.21  salary 49954  predicted ownership 75.42%  cheap players per row 1.77
  CHEAP2_BLOCK8   v2: P(>=1 big) 0.33098  expected big seats 0.50013  P(>=2) 0.11858  entry pct 0.51319  |  l02: P(>=1 big) 0.36286
                  book: projection per row 127.72  salary 49965  predicted ownership 76.53%  cheap players per row 1.59
  [2022]
  LIVE            v2: P(>=1 big) 0.21115  expected big seats 0.29504  P(>=2) 0.06750  entry pct 0.44654  |  l02: P(>=1 big) 0.22882
                  book: projection per row 132.25  salary 49969  predicted ownership nan%  cheap players per row 0.99
  CHEAP2          v2: P(>=1 big) 0.22490  expected big seats 0.28467  P(>=2) 0.05271  entry pct 0.45321  |  l02: P(>=1 big) 0.24710
                  book: projection per row 130.96  salary 49951  predicted ownership nan%  cheap players per row 2.28
  CHEAP4          v2: P(>=1 big) 0.20818  expected big seats 0.27074  P(>=2) 0.05033  entry pct 0.44336  |  l02: P(>=1 big) 0.22969
                  book: projection per row 128.84  salary 49921  predicted ownership nan%  cheap players per row 3.02
  CHEAP4_BLOCK8   v2: P(>=1 big) 0.20977  expected big seats 0.27772  P(>=2) 0.05827  entry pct 0.45321  |  l02: P(>=1 big) 0.23104
                  book: projection per row 131.25  salary 49953  predicted ownership nan%  cheap players per row 1.68
  CHEAP2_BLOCK8   v2: P(>=1 big) 0.20952  expected big seats 0.27989  P(>=2) 0.05817  entry pct 0.45279  |  l02: P(>=1 big) 0.23071
                  book: projection per row 131.82  salary 49963  predicted ownership nan%  cheap players per row 1.49
```

**Reading.**
- **The whole book: no decision adoptable.**
  - +2 is neutral: −1.2 points of P(≥ 1 big); ratio 0.892.
  - +4 costs a third of the expected big seats (ratio 0.665), leans negative in both read seasons, and 2022 contradicts
    it.
- **The blocks, by the frozen Saturday rule: neither is enterable.**
  - The +2 block is a knife edge: +0.4 points on 2023–24 and −0.16 on 2022, every interval wide across zero, about 6%
    fewer expected big seats.
  - The rule stops it on the 2022 sign, the same rule the matchup block passed. So there is no evidence for it, and
    little against it.
  - His own condition, "if study 53's block read doesn't contradict it", is not met.
- **The field pattern is an association with realized booms.** The frozen prospective reading (`4ceada3f`, re-pinned
  `ce13626d`) watches it in Weeks 5–8, descriptive only.
- Study 38's amendment-6f paper arms (MIXT_QA0_CHEAP2 / _CHEAP4) keep the real-field record from Week 5.

**What it means for Saturday.**
- The one block slot is the matchup block (study 51 ENTERABLE: not harmful, not better) or none.
- The decision is his. A cheap block would be an OVERRIDE of a frozen stop, written as such. Even then, its file goes
  through Friday's Week-5 union first.

## Addendum 162 (2026-10-07): study 54 (his live book against production's plain optimizer, P3's MEAN_MILP, in the harness): NO DIFFERENCE out of sample; every estimate favours his construction; nothing says to simplify

**Setup.**
- **The question.** The operator's approved-plan P3 (`reports/2026-10-07-prereg-p3-simple-baseline.md`, frozen
  `f129bc0b`) asks on live weeks whether our construction layers earn their place against production's plain capped
  optimizer. Its sign rule cannot decide before Week 12.
  - The operator, 10-07: "That is way too long for me to wait to adopt anything."
  - His yes, the same day: this harness answer, out of sample, read by Thursday.
- **The arms.**
  - **LIVE:** his live Week-5 book and production's 15 spares (study 48d's 41 rows: the winners' mix, the round-robin
    fill, QB cap 5, overlap limit 4, caps 13 / 6).
  - **PLAIN (the decision):** union_reselect's `pmo_rows`, copied verbatim (production's file `82ef245e…`): 26 rows,
    PRODUCTION_STACK, overlap 7, no QB cap, exposure 13, DST 6, per-game 4, $49k.
    - The smoke showed the Week-5 lab pin (`f69598b`) solves the same plain rows.
  - **PLAIN_O4 / PLAIN_O4Q5** (exploratory steps): PLAIN with the overlap limit 4, then also with the QB cap 5.
- **The decision is out of sample: the 17 2022 slates.**
  - Studies 35, 40, 41 and 42 chose the QB cap, the overlap limit and the fill on 2023–24.
  - Study 28 read the mix against the house shape once on 2022, on another harness.
  - 2023–24 is the in-sample read, never decision-bearing.
- **Support census:** PLAIN costs about −0.10 projected points per row. Its top QB sits in about 12 of 26 rows (LIVE 5),
  with about 4.1 distinct QBs (LIVE 7.7–8.1). The two books share 1.4–1.5 rows.
- **Preregistration:** `reports/2026-10-08-prereg-study54-plain-baseline.md` (DRAFT `eb97b570`; FROZEN `3c5bd444`,
  sha256 `81363694…`).
- **Panel:** banks 1575–1580, B 20,000, seed 20261106.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop**.
  - Reader `74fc1b3c`; READ `7af01d9b`; census `34fb1ce0`.
  - The confirmatory census (`72c80cb`) was committed before the READ (`2d9d18b`).

**Reader output (verbatim):**
```
STUDY 54 READER  sha256 74fc1b3cb0f18de65ea6a65c3a88aa9bfb320aba095466b5d327e31a3c2e58e4
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm (the decision PLAIN - LIVE: positive = production's plain optimizer ahead, negative = his live book ahead).
slates 17 (2022: THE DECISION, out of sample) + 36 (2023-24: in-sample, never decision-bearing)  banks [1575, 1576, 1577, 1578, 1579, 1580]  B 20000  seed 20261106  one decision (PLAIN - LIVE) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only
arms (definitions, the plain constants, study 48's sha, live settings, QB cap, objective): [["LIVE", "PLAIN", "PLAIN_O4", "PLAIN_O4Q5"], {"arms": {"PLAIN": [7, null], "PLAIN_O4": [4, null], "PLAIN_O4Q5": [4, 5]}, "caps": [13, 6], "copied_sha256": "bc3c0f74513e29d65e229e72d77ef403382d7c325296b147c061229854ed5199", "max_per_game": 4, "min_salary": 49000}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", {"fill": "rr", "max_shared": 4}, 5, "player_mean (every arm)"]

== PLAIN vs LIVE  [DECISION; the calibrated field; 2022, out of sample]
  PRIMARY P(>= 1 big seat) per slate -0.05331  [-0.14945, +0.03834] (two-sided 0.95)  seasons 2022 -0.05331
  GUARD 1 mean entry pct +0.00124  one-sided lower -0.01978  (must exceed -0.015)
  GUARD 2 expected big seats 0.57141 vs 0.36547  ratio 1.563  (must be >= 0.80)
  PLAIN dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  IN-SAMPLE 2023-24 (never decision-bearing; the selection favours LIVE): -0.06800  [-0.14877, +0.01179] (two-sided 0.95)  seasons 2023 -0.04464, 2024 -0.09136

== STUDY: NO EVIDENCE EITHER WAY out of sample (NO DIFFERENCE on 2022): his live book stands and P3's weekly record continues

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  PLAIN_O4 - PLAIN (the overlap limit 4; v2, 2022): +0.03711  [-0.01423, +0.09836]  seasons 2022 +0.03711
  PLAIN_O4 - PLAIN (the overlap limit 4; v2, 2023-24): +0.02464  [-0.03857, +0.09022]  seasons 2023 +0.05449, 2024 -0.00522
  PLAIN_O4Q5 - PLAIN_O4 (the QB cap 5; v2, 2022): -0.01417  [-0.04372, +0.01207]  seasons 2022 -0.01417
  PLAIN_O4Q5 - PLAIN_O4 (the QB cap 5; v2, 2023-24): +0.05209  [+0.02294, +0.09348]  seasons 2023 +0.04047, 2024 +0.06371
  LIVE - PLAIN_O4Q5 (the shape mix and the round-robin fill; v2, 2022): +0.03038  [-0.00662, +0.07804]  seasons 2022 +0.03038
  LIVE - PLAIN_O4Q5 (the shape mix and the round-robin fill; v2, 2023-24): -0.00872  [-0.06255, +0.04087]  seasons 2023 -0.05032, 2024 +0.03287
  PLAIN - LIVE (the l02 field, 2022): -0.06017  [-0.15825, +0.03321]  seasons 2022 -0.06017
  PLAIN - LIVE (the l02 field, 2023-24): -0.07954  [-0.16164, +0.00184]  seasons 2023 -0.05941, 2024 -0.09967
  PLAIN - LIVE (the l02 field, the 53-slate pool, 2022-24): -0.07332  [-0.13723, -0.00939]  seasons 2022 -0.06017, 2023 -0.05941, 2024 -0.09967
  PLAIN - LIVE (v2, the 53-slate pool, 2022-24; not a fresh test): -0.06329  [-0.12585, -0.00040]  seasons 2022 -0.05331, 2023 -0.04464, 2024 -0.09136

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2022]
  LIVE        v2: P(>=1 big) 0.24947  expected big seats 0.36547  P(>=2) 0.07733  entry pct 0.44316  |  l02: P(>=1 big) 0.26457
              book: projection per row 132.22  salary 49967  predicted ownership nan%  distinct QBs 7.7  top QB rows 5.0  distinct players 47.8
  PLAIN       v2: P(>=1 big) 0.19616  expected big seats 0.57141  P(>=2) 0.14143  entry pct 0.44440  |  l02: P(>=1 big) 0.20440
              book: projection per row 132.12  salary 49944  predicted ownership nan%  distinct QBs 4.1  top QB rows 11.8  distinct players 38.7
  PLAIN_O4    v2: P(>=1 big) 0.23327  expected big seats 0.42460  P(>=2) 0.09905  entry pct 0.44157  |  l02: P(>=1 big) 0.24683
              book: projection per row 131.41  salary 49960  predicted ownership nan%  distinct QBs 7.0  top QB rows 9.7  distinct players 52.6
  PLAIN_O4Q5  v2: P(>=1 big) 0.21910  expected big seats 0.37097  P(>=2) 0.08659  entry pct 0.43807  |  l02: P(>=1 big) 0.23647
              book: projection per row 131.12  salary 49960  predicted ownership nan%  distinct QBs 8.4  top QB rows 5.0  distinct players 55.7
  [2023-24]
  LIVE        v2: P(>=1 big) 0.31333  expected big seats 0.51527  P(>=2) 0.12258  entry pct 0.51452  |  l02: P(>=1 big) 0.34272
              book: projection per row 128.15  salary 49971  predicted ownership 78.21%  distinct QBs 8.1  top QB rows 5.0  distinct players 46.1
  PLAIN       v2: P(>=1 big) 0.24533  expected big seats 0.44378  P(>=2) 0.12472  entry pct 0.51161  |  l02: P(>=1 big) 0.26318
              book: projection per row 128.05  salary 49951  predicted ownership 79.53%  distinct QBs 4.1  top QB rows 12.0  distinct players 37.8
  PLAIN_O4    v2: P(>=1 big) 0.26997  expected big seats 0.38625  P(>=2) 0.08616  entry pct 0.49066  |  l02: P(>=1 big) 0.29658
              book: projection per row 127.25  salary 49961  predicted ownership 77.26%  distinct QBs 7.5  top QB rows 8.9  distinct players 51.1
  PLAIN_O4Q5  v2: P(>=1 big) 0.32206  expected big seats 0.47978  P(>=2) 0.11340  entry pct 0.50038  |  l02: P(>=1 big) 0.35082
              book: projection per row 127.02  salary 49961  predicted ownership 76.34%  distinct QBs 8.7  top QB rows 5.0  distinct players 53.9
```

**Reading.**
- **The decision: NO DIFFERENCE out of sample, so no evidence either way.**
  - On 2022, P(≥ 1 big seat) per week was 0.249 for his live book and 0.196 for the plain optimizer: −5.3 points, with
    the interval wide across zero.
- **Every estimate favours his construction:**
  - 2022 −0.053;
  - 2023 −0.045;
  - 2024 −0.091;
  - the 53-slate pool (exploratory, not a fresh test) −0.063 [−0.126, −0.0004].
- **The plain book wins MORE seats in total on 2022 (0.571 vs 0.365 a week), but less often.**
  - Its top QB fills about 12 of 26 rows, so its hits cluster: P(≥ 2) is 0.141 vs 0.077.
  - On his goal, at least one big win a week, the live shape is the better one.
- **The exploratory steps** (indicative only):

  | step | 2022 | 2023–24 |
  |---|---|---|
  | the overlap limit 4 | +0.037 | +0.025 |
  | the QB cap 5 | −0.014 | +0.052 |
  | the shape mix and the round-robin fill | +0.030 | −0.009 |

  The QB cap's in-sample gain does not replicate on 2022.

**What it means.**
- Nothing says to simplify. The live construction stays.
- P3's weekly real-field record (ENTERED vs MEAN_MILP) continues as the live check. The laptop's Week 2–4 replay
  (reconstructed, in-sample, descriptive) tied on big seats in all three weeks.

## Addendum 163 (2026-10-07): study 56 (fewer QB+1 rows in his live book): NO DIFFERENCE, not contradicted; not adoptable; on paper in Week 5 by his own line

**Setup.**
- **The question.** The outside reviewer's satellite finding: QB+1 lineups reached a top-10% finish less often than
  QB+2 (odds 0.83 [0.74, 0.93]; W1–4, 76 satellite and qualifier contests). His live book deals about 48% of its entries
  to QB+1 rows.
- **The arms.** His live book (study 48d's 41 rows) at three sets of cell quotas:
  - LIVE: A1 0.30 / A2 0.14 / B 0.28 / C 0.28;
  - QB2HALF (the decision): 0.44 / 0.28 / 0.14 / 0.14, half of each QB+1 cell moved to its QB+2 counterpart;
  - QB2ALL: 0.58 / 0.42 / 0 / 0;
  - and, exploratory, LIVE_CB / QB2HALF_CB with Week 5's live cheap +2 block.
- **Support census:** dealt QB+1 goes from .48 to .26 (QB2HALF), at −0.26 projected points per row; QB2HALF shares 4 of
  26 rows with LIVE.
- **His Week-5 line** (10-07, frozen before the read): "If it doesn't seem like it will improve things, I don't want to
  do it this week. But I do think it's worth a test to find out as planned." Live only on a PASS that is not
  contradicted.
- **Preregistration:** `reports/2026-10-08-prereg-study56-fewer-qb1.md` (DRAFT `895cb346`, committed before study 54's
  read; FROZEN `19db7b43`, sha256 `8fd8805f…`).
- **Panel:** banks 1581–1586, B 20,000, seed 20261107.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop**.
  - Reader `38fb00d7`; READ `d2b0fe17`; census `eeb04d4f`.
  - The confirmatory census (`8d70119`) was committed before the READ (`d1f3d28`).
- **Production's vehicle:** `union_reselect --mix-cell-quotas` (integration `48946cd0`, default off).
- **Study 38's paper arm:** MIXT_QA0_QB2HALF (amendment 6j).

**Reader output (verbatim):**
```
STUDY 56 READER  sha256 38fb00d768012390c4d08597706e1ff7affbc8da745c6c7174cbebc1185c6d1f
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1581, 1582, 1583, 1584, 1585, 1586]  B 20000  seed 20261107  one decision (QB2HALF - LIVE) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval); the plan's satellites: 28 of 29 contests
arms (definitions, the quotas, the cells, the block, study 48's sha, live settings, QB cap, objective): [["LIVE", "QB2HALF", "QB2ALL", "LIVE_CB", "QB2HALF_CB"], {"LIVE": [0.3, 0.14, 0.28, 0.28], "QB2ALL": [0.58, 0.42, 0.0, 0.0], "QB2HALF": [0.44, 0.28, 0.14, 0.14]}, ["A1", "A2", "B", "C"], {"arms": {"LIVE_CB": "LIVE", "QB2HALF_CB": "QB2HALF"}, "cap": 2.0, "dose": 2.0, "n_term": 8, "s53_sha256": "f3f9d735ca0c5dfadb7abe6c2999fd3bcb352425e4fcc7ea73bd2b09d4522c89"}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", {"fill": "rr", "max_shared": 4}, 5, "player_mean (every arm)"]

== QB2HALF vs LIVE  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate +0.01846  [-0.02489, +0.06469] (two-sided 0.95)  seasons 2023 +0.02888, 2024 +0.00803
  GUARD 1 mean entry pct -0.00632  one-sided lower -0.01149  (must exceed -0.015)
  GUARD 2 expected big seats 0.56890 vs 0.55808  ratio 1.019  (must be >= 0.80)
  QB2HALF dealt identical to LIVE: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.02170  [-0.03679, +0.08300] (two-sided 0.95)  ->  not contradicted

== STUDY: not adoptable: QB2HALF NO DIFFERENCE on 2023-24, not contradicted on 2022
== TRIAL (study 51's rule, the adoption track v2): ENTERABLE, his decision: no harm shown and no gain shown (NO DIFFERENCE on the read, not contradicted on 2022)

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  QB2ALL - LIVE (v2, 2023-24): +0.01616  [-0.04211, +0.07737]  seasons 2023 +0.00598, 2024 +0.02634
  QB2ALL - LIVE (v2, 2022): +0.00444  [-0.02604, +0.03909]  seasons 2022 +0.00444
  QB2HALF_CB - LIVE_CB (the tilt beside the cheap +2 block; v2, 2023-24): +0.02361  [-0.02904, +0.07634]  seasons 2023 +0.02851, 2024 +0.01872
  QB2HALF_CB - LIVE_CB (the tilt beside the cheap +2 block; v2, 2022): -0.00765  [-0.04340, +0.02656]  seasons 2022 -0.00765
  QB2HALF - LIVE (the plan's satellites only, v2, 2023-24): +0.01846  [-0.02489, +0.06469]  seasons 2023 +0.02888, 2024 +0.00803
  QB2HALF - LIVE (the plan's satellites only, v2, 2022): +0.02170  [-0.03679, +0.08300]  seasons 2022 +0.02170
  QB2ALL - LIVE (the plan's satellites only, v2, 2023-24): +0.01616  [-0.04211, +0.07737]  seasons 2023 +0.00598, 2024 +0.02634
  QB2ALL - LIVE (the plan's satellites only, v2, 2022): +0.00444  [-0.02604, +0.03909]  seasons 2022 +0.00444
  QB2HALF - LIVE (the l02 field, 2023-24): +0.01684  [-0.02626, +0.06320]  seasons 2023 +0.02906, 2024 +0.00463
  QB2HALF - LIVE (the l02 field, 2022): +0.03067  [-0.02296, +0.08986]  seasons 2022 +0.03067

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2023-24]
  LIVE       v2: P(>=1 big) 0.35466  expected big seats 0.55808  P(>=2) 0.13405  entry pct 0.52160  satellites P(>=1 big) 0.35466  |  l02: P(>=1 big) 0.38605
             book: projection per row 128.12  salary 49971  predicted ownership 78.59%  dealt QB+1 / +2 / +3+ 0.486 / 0.472 / 0.042  distinct QBs 8.1
  QB2HALF    v2: P(>=1 big) 0.37312  expected big seats 0.56890  P(>=2) 0.13588  entry pct 0.51528  satellites P(>=1 big) 0.37312  |  l02: P(>=1 big) 0.40289
             book: projection per row 127.85  salary 49970  predicted ownership 78.18%  dealt QB+1 / +2 / +3+ 0.269 / 0.662 / 0.069  distinct QBs 8.3
  QB2ALL     v2: P(>=1 big) 0.37082  expected big seats 0.57098  P(>=2) 0.14260  entry pct 0.51023  satellites P(>=1 big) 0.37082  |  l02: P(>=1 big) 0.39910
             book: projection per row 127.46  salary 49966  predicted ownership 77.73%  dealt QB+1 / +2 / +3+ 0.000 / 0.897 / 0.103  distinct QBs 8.4
  LIVE_CB    v2: P(>=1 big) 0.32032  expected big seats 0.49749  P(>=2) 0.12336  entry pct 0.51626  satellites P(>=1 big) 0.32021  |  l02: P(>=1 big) 0.34578
             book: projection per row 127.71  salary 49965  predicted ownership 76.91%  dealt QB+1 / +2 / +3+ 0.465 / 0.495 / 0.040  distinct QBs 8.4
  QB2HALF_CB v2: P(>=1 big) 0.34393  expected big seats 0.53419  P(>=2) 0.13338  entry pct 0.50938  satellites P(>=1 big) 0.34393  |  l02: P(>=1 big) 0.37210
             book: projection per row 127.42  salary 49962  predicted ownership 76.52%  dealt QB+1 / +2 / +3+ 0.240 / 0.694 / 0.067  distinct QBs 8.7
  [2022]
  LIVE       v2: P(>=1 big) 0.23722  expected big seats 0.35022  P(>=2) 0.08118  entry pct 0.44458  satellites P(>=1 big) 0.23722  |  l02: P(>=1 big) 0.25312
             book: projection per row 132.30  salary 49967  predicted ownership nan%  dealt QB+1 / +2 / +3+ 0.482 / 0.464 / 0.054  distinct QBs 7.7
  QB2HALF    v2: P(>=1 big) 0.25892  expected big seats 0.39811  P(>=2) 0.10418  entry pct 0.43943  satellites P(>=1 big) 0.25892  |  l02: P(>=1 big) 0.28379
             book: projection per row 132.08  salary 49964  predicted ownership nan%  dealt QB+1 / +2 / +3+ 0.264 / 0.661 / 0.075  distinct QBs 7.8
  QB2ALL     v2: P(>=1 big) 0.24166  expected big seats 0.40237  P(>=2) 0.10291  entry pct 0.43666  satellites P(>=1 big) 0.24166  |  l02: P(>=1 big) 0.25752
             book: projection per row 131.77  salary 49964  predicted ownership nan%  dealt QB+1 / +2 / +3+ 0.000 / 0.884 / 0.116  distinct QBs 7.9
  LIVE_CB    v2: P(>=1 big) 0.23536  expected big seats 0.33307  P(>=2) 0.07916  entry pct 0.44988  satellites P(>=1 big) 0.23536  |  l02: P(>=1 big) 0.25655
             book: projection per row 131.87  salary 49961  predicted ownership nan%  dealt QB+1 / +2 / +3+ 0.464 / 0.486 / 0.050  distinct QBs 7.9
  QB2HALF_CB v2: P(>=1 big) 0.22771  expected big seats 0.34785  P(>=2) 0.08545  entry pct 0.45046  satellites P(>=1 big) 0.22771  |  l02: P(>=1 big) 0.24819
             book: projection per row 131.63  salary 49957  predicted ownership nan%  dealt QB+1 / +2 / +3+ 0.243 / 0.684 / 0.073  distinct QBs 8.1
```

**Reading.**
- **No difference.** P(≥ 1 big seat) per week 0.373 vs 0.355 on 2023–24 (+1.8 points, interval −2.5 to +6.5). Both
  seasons and 2022 lean the same way (+2.9 / +0.8 / +2.2). Expected big seats are unchanged (ratio 1.02).
- **Not adoptable, so it stays on paper in Week 5 by his line.** The trial rule says ENTERABLE (no harm shown), which
  makes it a Week-6 trial option if he wants one.
- The tilt beside the cheap block is the same story (+2.4 / −0.8).
- **Descriptive only:** LIVE_CB vs LIVE read 0.320 vs 0.355 on 2023–24 and 0.235 vs 0.237 on 2022 on these banks. Study
  53's frozen read of the same block, on other banks, was +0.004. Two harness samples show no gain. The live trial's stop
  rule watches the real weeks.

## Addendum 164 (2026-10-07): study 57 (R4 joint coverage for his five 2-entry contests): NO DIFFERENCE, leaning negative; not supported; not for Week 5 or 6

**Setup.**
- **The question.** Study 32 offered R4 (Addendum 137): the m rows of a finished book most likely to put at least one
  entry in a contest's top S, chosen against a pre-lock field. His priorities for the week named it second after study
  56.
- **The arms.** One book: his live book with the cheap +2 block (LIVE_CB), on his final plan Rev6 (`ac10ddf6`).
  - CB: the head deal.
  - **CB_R4 (the decision):** each of the five unpinned 2-entry big contests ($555 2x, three $333 Wildcats, the
    Millionaire) takes R4's pair, chosen sequentially in Rev6 order over the rows not yet taken. Every other contest keeps
    its head deal.
  - CB_PRI / CB_PRI_R4: the same with production's priority order.
- **The decision pair** was fixed by his arming: the priority order was not armed (the laptop's screen), so it is
  CB_R4 − CB.
- **Two smoke fixes before the freeze:**
  - five pins alone re-blocked six other contests, moving his Warm Up sats from ranks 20–22 to 14–16;
  - independent picks gave the three Wildcats the same pair (the laptop's catch).
- **Production parity:** `entry_choice.joint_coverage`, with the same exclusions, picked the same pairs.
- **Preregistration:** `reports/2026-10-08-prereg-study57-r4-pairs.md` (FROZEN `60a6474e`, sha256 `171040df…`).
- **Panel:** banks 1593–1598, B 20,000, seed 20261109; 2023–24 only (the pre-lock field needs predicted ownership).
- **Disclosed:** in-sample for the rule (study 32 chose R4 on these slates). The frozen reader's STUDY line names
  "CB_R4" for the second pair too, a cosmetic string.
- **Read and reproduced:** read by the reviewer and **reproduced byte-identically by the laptop**.
  - Reader `d7fedb91`; READ `6cb3d24c`; census `00d2a5a6`.
  - The confirmatory census (`53f7ecb`) was committed before the READ (`a536d35`).

**Reader output (verbatim):**
```
STUDY 57 READER  sha256 d7fedb91d73243ba52e09b2a3b36f7da0438c2e85e792ddd93512ff31561c633
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (2023-24; no 2022 go / no-go)  banks [1593, 1594, 1595, 1596, 1597, 1598]  B 20000  seed 20261109  one decision (CB_R4 - CB) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; the R4 contests: 5 of 29; DISCLOSED: in-sample for the rule (study 32 chose R4 on these slates)
arms (definitions, R4, the block, study 48's and 32's shas, live settings, QB cap, objective): [["CB", "CB_R4", "CB_PRI", "CB_PRI_R4"], {"contests": ["supersat", "wildcat", "wildcat2", "wildcat3", "milly"], "field_sim": 20000, "m": 2, "sel_own": "TABPFN_LS", "w_sim": 1000}, {"cap": 2.0, "dose": 2.0, "n_term": 8, "s53_sha256": "f3f9d735ca0c5dfadb7abe6c2999fd3bcb352425e4fcc7ea73bd2b09d4522c89"}, "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", "06c35b9ae2a5e3472f7c882709a5f0070a382d325162df06d0ba7d31e70730dd", {"fill": "rr", "max_shared": 4}, 5, "player_mean"]

== CB_R4 vs CB  [DECISION when the priority order NOT armed; the calibrated field; 2023-24]
  PRIMARY P(>= 1 big seat) per slate -0.01637  [-0.03865, +0.00448] (two-sided 0.95)  seasons 2023 -0.02130, 2024 -0.01145
  GUARD 1 mean entry pct -0.00245  one-sided lower -0.00517  (must exceed -0.015)
  GUARD 2 expected big seats 0.55029 vs 0.53066  ratio 1.037  (must be >= 0.80)
  CB_R4 dealt identical to CB: 0.000 of slate-banks
  ->  NO DIFFERENCE
  STUDY: not supported: CB_R4 NO DIFFERENCE on 2023-24
  TRIAL (study 51's rule without its 2022 clause, the adoption track v2): ENTERABLE, his decision: no harm shown and no gain shown (NO DIFFERENCE on the read)

== CB_PRI_R4 vs CB_PRI  [DECISION when the priority order ARMED; the calibrated field; 2023-24]
  PRIMARY P(>= 1 big seat) per slate -0.01595  [-0.04031, +0.00690] (two-sided 0.95)  seasons 2023 -0.03151, 2024 -0.00040
  GUARD 1 mean entry pct +0.00010  one-sided lower -0.00309  (must exceed -0.015)
  GUARD 2 expected big seats 0.53560 vs 0.52735  ratio 1.016  (must be >= 0.80)
  CB_PRI_R4 dealt identical to CB_PRI: 0.000 of slate-banks
  ->  NO DIFFERENCE
  STUDY: not supported: CB_R4 NO DIFFERENCE on 2023-24
  TRIAL (study 51's rule without its 2022 clause, the adoption track v2): ENTERABLE, his decision: no harm shown and no gain shown (NO DIFFERENCE on the read)

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  CB_R4 - CB (the five R4 contests only, v2, 2023-24): -0.00203  [-0.04052, +0.03752]  seasons 2023 -0.01421, 2024 +0.01016
  CB_PRI_R4 - CB_PRI (the five R4 contests only, v2, 2023-24): +0.00229  [-0.04185, +0.04691]  seasons 2023 -0.02128, 2024 +0.02587
  CB_PRI - CB (the five R4 contests only, v2, 2023-24): -0.00432  [-0.03846, +0.02794]  seasons 2023 +0.00707, 2024 -0.01571
  CB_PRI - CB (the priority order alone, v2, 2023-24): +0.00459  [-0.02400, +0.03643]  seasons 2023 -0.00537, 2024 +0.01454
  CB_R4 - CB (the l02 field, 2023-24): -0.01972  [-0.04294, +0.00212]  seasons 2023 -0.02323, 2024 -0.01620

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field):
  CB        v2: P(>=1 big) 0.34064  expected big seats 0.53066  P(>=2) 0.12593  entry pct 0.51545  the R4 contests P(>=1 big) 0.16739  |  l02: P(>=1 big) 0.36917
  CB_R4     v2: P(>=1 big) 0.32427  expected big seats 0.55029  P(>=2) 0.13699  entry pct 0.51300  the R4 contests P(>=1 big) 0.16536  |  l02: P(>=1 big) 0.34945
  CB_PRI    v2: P(>=1 big) 0.34523  expected big seats 0.52735  P(>=2) 0.12599  entry pct 0.51024  the R4 contests P(>=1 big) 0.16307  |  l02: P(>=1 big) 0.37420
  CB_PRI_R4 v2: P(>=1 big) 0.32927  expected big seats 0.53560  P(>=2) 0.13537  entry pct 0.51034  the R4 contests P(>=1 big) 0.16536  |  l02: P(>=1 big) 0.35515
```

**Reading.**
- **No difference, leaning against.** P(≥ 1 big seat) per week was 0.324 with R4's pairs against 0.341 with the head deal
  (−1.6 points, interval −3.9 to +0.4); both seasons are negative.
- **R4 shifts wins rather than adding them.** It raises P(≥ 2) (0.137 vs 0.126) and expected seats (ratio 1.04). In the
  five contests alone it changes nothing (−0.002). Optimizing each pair seems to correlate the contests' results.
- **Not supported; not for Week 5 or Week 6.** It fails his study-56 bar, and it leans the wrong way on his utility. The
  Sunday step need not be built.

## Addendum 165 (2026-10-07): study 59 (priority-first dealing on his Rev6 plan, a Week-6 read): NO DIFFERENCE, not contradicted; not supported; with the in-sample screen's harm, not recommended

**Setup.**
- **The question.** The operator, 10-07: "Let's try to do this one this week." The book does not change. His priority
  contests read the rows that score highest on a frozen pre-lock score: +2 if the QB has 2+ teammates, +1 for a
  bring-back, +1 for two or more sub-$4,000 non-DST players. The block's 8 rows keep their positions.
- **The arms.** Every arm is dealt on his final plan Rev6 (`ac10ddf6`). The order is production's `priority_deal.py`
  (`fa47594d`, copied verbatim, with parity checked on 200 random books and on the real rows).
  - CB: his live book with the cheap +2 block, in its own order.
  - **CB_PRI (the decision):** the same book, priority-ordered.
  - LIVE / PRI_ALL: the whole-book form without the block (exploratory).
- **The laptop's frozen W2–4 in-sample harm screen** (`27a1957b`; amendment 1 `7ee09fe1`) said NOT ENTERED: lower in 2
  of 3 weeks, seats ratio 0.587. So the order is not armed for Week 5, and this is the Week-6 read.
- **Preregistration:** `reports/2026-10-08-prereg-study59-priority-deal.md` (DRAFT `6d8967f2`, committed before study
  56's read; FROZEN `4534b1c6`, sha256 `4dafb0b7…`).
- **Panel:** banks 1587–1592, B 20,000, seed 20261108.
- **Read:** the reader `c6b70771`; READ `74463caf`. The confirmatory census (`ecf8f2c`) was committed before the READ
  (`030e7a9`). **Reproduced byte-identically by the laptop** (census `c56b7bd3`).

**Reader output (verbatim):**
```
STUDY 59 READER  sha256 c6b70771acadd5a35880d85f4eaa86cd626b55451bc043b22b203964e78f31ad
DIRECTION: P(>= 1 big seat) per slate (the mean over its banks); every difference is ARM - REFERENCE; POSITIVE favours the first arm.
slates 36 (the 2023-24 read) + 17 (the 2022 go / no-go)  banks [1587, 1588, 1589, 1590, 1591, 1592]  B 20000  seed 20261108  one decision (CB_PRI - CB) on the CALIBRATED field (v2), two-sided 0.95, guard 1 one-sided 0.95 at -0.015, guard 2 ratio >= 0.80; the guards gate a PASS only; 2022: the point estimate (two-sided 0.95 interval); big contests 21 of 29
arms (definitions, the deals, the block, the score, study 48's sha, live settings, QB cap, objective): [["CB", "CB_PRI", "LIVE", "PRI_ALL"], {"CB": ["LIVE_CB", "book"], "CB_PRI": ["LIVE_CB", "priority"], "LIVE": ["LIVE", "book"], "PRI_ALL": ["LIVE", "priority"]}, {"cap": 2.0, "dose": 2.0, "n_term": 8, "s53_sha256": "f3f9d735ca0c5dfadb7abe6c2999fd3bcb352425e4fcc7ea73bd2b09d4522c89"}, "+2 QB 2+ teammates, +1 bring-back, +1 2+ non-DST under 4000", "c22d28114ab4b463b6842594cb2ff7ca1babf41e28015c7242b21baedb1bc67c", {"fill": "rr", "max_shared": 4}, 5, "player_mean (every book)"]

== CB_PRI vs CB  [DECISION; the calibrated field; the 2023-24 read]
  PRIMARY P(>= 1 big seat) per slate +0.00685  [-0.01634, +0.03173] (two-sided 0.95)  seasons 2023 +0.00230, 2024 +0.01140
  GUARD 1 mean entry pct -0.00482  one-sided lower -0.00820  (must exceed -0.015)
  GUARD 2 expected big seats 0.51653 vs 0.51895  ratio 0.995  (must be >= 0.80)
  CB_PRI dealt identical to CB: 0.000 of slate-banks
  ->  NO DIFFERENCE
  GO / NO-GO 2022: +0.01469  [-0.01849, +0.06034] (two-sided 0.95)  ->  not contradicted

== STUDY: not supported: CB_PRI NO DIFFERENCE on 2023-24, not contradicted on 2022
== TRIAL (study 51's rule, the adoption track v2): ENTERABLE, his decision: no harm shown and no gain shown (NO DIFFERENCE on the read, not contradicted on 2022)

== EXPLORATORY (never decision-bearing; two-sided 0.95)
  PRI_ALL - LIVE (the whole-book form, no block; v2, 2023-24): +0.01360  [-0.01847, +0.04507]  seasons 2023 +0.01276, 2024 +0.01443
  PRI_ALL - LIVE (the whole-book form, no block; v2, 2022): -0.03670  [-0.09414, +0.00533]  seasons 2022 -0.03670
  CB_PRI - CB (the l02 field, 2023-24): +0.00681  [-0.01830, +0.03440]  seasons 2023 +0.00276, 2024 +0.01086
  CB_PRI - CB (the l02 field, 2022): +0.01406  [-0.01992, +0.05986]  seasons 2022 +0.01406

secondaries (slate means; v2 = the calibrated field, l02 = the earlier field; the book's rows are pre-lock facts):
  [2023-24]
  CB       v2: P(>=1 big) 0.32348  expected big seats 0.51895  P(>=2) 0.12452  entry pct 0.51158  |  l02: P(>=1 big) 0.35277
           book: projection per row 127.73  salary 49964  score per dealt entry 2.130
  CB_PRI   v2: P(>=1 big) 0.33033  expected big seats 0.51653  P(>=2) 0.12644  entry pct 0.50676  |  l02: P(>=1 big) 0.35958
           book: projection per row 127.73  salary 49964  score per dealt entry 2.320
  LIVE     v2: P(>=1 big) 0.30663  expected big seats 0.48569  P(>=2) 0.12008  entry pct 0.51563  |  l02: P(>=1 big) 0.33473
           book: projection per row 128.15  salary 49970  score per dealt entry 1.888
  PRI_ALL  v2: P(>=1 big) 0.32023  expected big seats 0.50749  P(>=2) 0.12227  entry pct 0.50856  |  l02: P(>=1 big) 0.34992
           book: projection per row 128.15  salary 49970  score per dealt entry 2.183
  [2022]
  CB       v2: P(>=1 big) 0.21272  expected big seats 0.29345  P(>=2) 0.06658  entry pct 0.45547  |  l02: P(>=1 big) 0.23051
           book: projection per row 131.86  salary 49962  score per dealt entry 2.089
  CB_PRI   v2: P(>=1 big) 0.22741  expected big seats 0.33029  P(>=2) 0.07602  entry pct 0.45117  |  l02: P(>=1 big) 0.24458
           book: projection per row 131.86  salary 49962  score per dealt entry 2.260
  LIVE     v2: P(>=1 big) 0.24576  expected big seats 0.32664  P(>=2) 0.06217  entry pct 0.45202  |  l02: P(>=1 big) 0.26525
           book: projection per row 132.28  salary 49968  score per dealt entry 1.847
  PRI_ALL  v2: P(>=1 big) 0.20906  expected big seats 0.32285  P(>=2) 0.08047  entry pct 0.45119  |  l02: P(>=1 big) 0.22450
           book: projection per row 132.28  salary 49968  score per dealt entry 2.123
```

**Reading.**
- **No difference.** P(≥ 1 big seat) per week was 0.330 against 0.323 on 2023–24 (+0.7 points, interval −1.6 to +3.2).
  2022 leans the same way (+1.5), and expected seats are unchanged (ratio 0.995).
- **Not supported.** The trial rule says ENTERABLE, but on his real Weeks 2–4 the in-sample screen showed harm. My
  advice for Week 6 is not to use it.
- **The whole-book form** (no block, all 26 rows sorted): +1.4 on 2023–24, −3.7 on 2022.
- **Descriptive, the third harness sample of the cheap +2 block** (CB vs LIVE, both in book order): 2023–24 0.323 vs
  0.307, 2022 0.213 vs 0.246. Across studies 53 / 56 / 59 the 2023–24 differences are +0.4 / −3.5 / +1.7, centred near
  zero. His Week-5 trial and Monday's comparison are the real-week test.
