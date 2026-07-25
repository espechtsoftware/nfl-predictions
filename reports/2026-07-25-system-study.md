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

Not yet implemented; measured next via replay once built.
