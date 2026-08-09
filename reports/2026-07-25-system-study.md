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
| XSCHED (XFP + SCHED) | 24 (+6) | 178.5 | 15.2 | = SCHED alone; XFP doesn't stack |
| XFP | 20 (+2) | 179.4 | 14.8 | positive alone; stays candidate |
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

The accepted K=3 true-80 book has 16 unselected candidate rows scoring at
least 200, but ten are redundant to a different selected 200+ lineup on the
same slate. Only six candidate rows across four weeks represent a lost
threshold opportunity. This distinction prevents impressive unselected raw
scores from overstating the actionable gap.

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
