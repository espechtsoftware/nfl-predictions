# B6 — What does a "dumb baseline" book score?

Written 2026-09-29 (research analyst, read-only pass; scripts in `B6/`, raw results in `B6/out/*.json`,
logs in `B6/out/run*.log`). No simulator, no multiprocessing, one CBC solve at a time, ~50 minutes of solver
wall time in total. No dollar figures. Nothing about 2026 Week 4 was read or computed.

## 1. What was built

For each live frame, three "dumb" books of K = 36 rows each, plus three co-reports, all built by sequential
MILP solves with `nfl2.core.lineup.optimize` (lab worktree `prereg-l19-20260929`, unmodified) under plain
DraftKings rules only: 1 QB / 2-3 RB / 3-4 WR / 1-2 TE / FLEX / 1 DST, salary cap 50,000, at most 8 from one team,
at least 2 games, each new row shares at most 7 players with every earlier row (`banned_lineups` + `max_overlap=7`).
No stack mandate, no bring-back, no salary floor (`min_salary=0`), no punt mandate, no ownership fade, no
`MAX_PER_GAME` (`env={}` so no environment lever fires).

| book | objective column | who is in the pool |
|---|---|---|
| **market** | `market_points` (de-vigged prop-implied DK points) | skill players that have a props number (192-221 per slate); DST valued at the served DST projection (there is no DST prop market) |
| **dk_ppg** | `dk_ppg` (DraftKings' own points-per-game from the draftables feed) | every row with a non-null figure (306-374) |
| **served** | `proj` (= `mean_projection`; the 0.45 model / 0.55 market blend the machine centres on) | the whole frame |
| model_pre (co-report) | `model_points_pre` (our model before the market blend) | whole frame |
| served_house (co-report) | `proj` + the house construction rules: salary floor 49,000, `StackRules(qb_stack_min=2, bring_back_min=1)` | whole frame |
| tourney_house (co-report) | `proj_tourney` (served projection with the sub-4,000 p90 punt valuation) + house rules | whole frame |

Comparators scored with the *same* actuals and scorer: the run directory's own `book.csv` (the machine's
expected-max selection, all rows and its first 36 rows), and the post-mortem figures for the entered book and the
top-mean counterfactual.

Frames (each is the frame the machine actually built from):

| tag | run | frame `pulled_at` (UTC) | rows | cash line used |
|---|---|---|---|---|
| w1 | `week1-live-center-e7255e9/…/2026-w01/20260913T160405364118Z-e7255e9` (K90 source of the entered v6b) | 2026-09-13 16:02 (Sunday, 58 min before lock) | 367 | 165.5 (Millionaire, settlement report §1) |
| w2 | `week2-release-2dc116c/…/2026-w02/20260919T153008787414Z-2dc116c` (the entered D12800) | 2026-09-19 14:42 (Saturday) | 429 | 138 |
| w3sat | `week3-live-center/…/2026-w03/20260926T153408285093Z-65305f5` (entered Saturday D12800) | 2026-09-26 15:29 (Saturday) | 421 | 149.5 |
| w3t70 | `week3-live-center/…/2026-w03/20260927T155027472554Z-65305f5` (Sunday T-70 D800) | 2026-09-27 15:29 (Sunday) | 439 | 149.5 |

Actuals (post-game, used for scoring only): Week 1 `~/week3-sunday/postmortem/w1_actuals.csv` (DK standings
export, 362 of 367 frame names matched; the five unmatched are long snappers and practice-squad names nobody drafted);
Week 3 `players_actuals.csv` (346/421 and 361/439 matched; unmatched are third-string QBs, fullbacks, long
snappers); Week 2 the union of the 12 DK standings exports under `~/week2-sunday/ENTERED/standings/` (Player/FPTS
columns; DST names carry a trailing space in the export and were stripped; 368/429 matched). A rostered player with
no actual is scored 0 and counted in `missing_actual_slots`; it happened only in Week 2 (7 slots in the served book,
all backup QBs / practice-squad names who did not play, so 0 is the right value).

## 2. Information time of every input

- `market_points`: production `nfl_dfs.models.prop_market.market_points` reads `nfl_raw.prop_lines` and keeps
  only snapshots before the Sunday-main first kickoff (`latest_pre_main_lock`); in a Saturday / T-70 frame it can
  only contain snapshots that existed at the frame's `pulled_at`. Pre-lock. Yes.
- `dk_ppg`: DK `draftStatAttributes` id 90 from the same salary pull as the frame (`ingest/dk_client.py`). Pre-lock.
  Caveat: in Week 1 it is the prior season's average (319 of 391 rows had one); in Week 2 it is a one-game figure
  (max 38.3), which is why the dk_ppg book's own projected sum is 275 in Week 2 and 215 in Week 3 — it is a season
  average, not a forecast.
- `proj` / `mean_projection` / `model_points_pre` / `proj_tourney`: produced at build from point-in-time features;
  pre-lock by construction (the frame's `pulled_at`).
- Cash lines and actuals: post-game, scoring only.

## 3. Live weeks, K = 36, plain DK rules (mean / median / best / share above the Millionaire cash line / share >= 150 / share >= 194)

### Week 1 (frame 2026-09-13 16:02Z; cash line 165.5)

| book | mean | median | best | >= cash | >= 150 | >= 194 | note |
|---|---:|---:|---:|---:|---:|---:|---|
| **market** (plain) | **157.1** | 156.1 | 190.1 | 0.36 | 0.64 | 0.00 | pool 192 |
| dk_ppg (plain) | 128.4 | 126.6 | 162.8 | 0.00 | 0.14 | 0.00 | prior-season averages |
| served (plain) | 132.2 | 132.1 | 183.1 | 0.06 | 0.11 | 0.00 | 36 distinct players, mean pairwise overlap 5.7; Chase in 36/36 (scored 3.2), Kyler Murray 33/36 (0.6) |
| served, market universe only | 132.2 | 132.1 | 183.1 | 0.06 | 0.11 | 0.00 | identical book: the served top players all had props |
| model_pre (plain) | 130.8 | 132.9 | 161.7 | 0.00 | 0.19 | 0.00 | |
| served + house rules | 172.1 | 174.3 | 210.1 | 0.67 | 0.92 | 0.14 | stack + bring-back + floor |
| proj_tourney + house rules | 144.0 | 142.8 | 186.4 | 0.08 | 0.28 | 0.00 | punt valuation costs 28 |
| machine book.csv, K90 (expected-max) | 144.6 | 141.5 | 224.5 | 0.22 | 0.40 | 0.02 | same scorer |
| machine book.csv, first 36 | 148.1 | 148.3 | 203.8 | 0.31 | 0.50 | 0.03 | |
| entered v6b, 80 rows (settlement report) | 144.9 | – | 196.2 | 0.23 | – | 0 | post-mortem §6.1 quotes 146.6 / 30% / 207.1 |
| top-mean counterfactual, K80 (post-mortem §6.1) | 169.7 | – | 214.5 | 0.55 | – | – | same pool, sorted by mean |

### Week 2 (frame 2026-09-19 14:42Z; cash line 138) — the served projections carry the known availability / prop-name defects; not a clean projection test

| book | mean | median | best | >= cash | >= 150 | >= 194 | note |
|---|---:|---:|---:|---:|---:|---:|---|
| **market** (plain) | **112.5** | 112.9 | 161.7 | 0.06 | 0.03 | 0.00 | pool 203 |
| dk_ppg (plain) | 108.7 | 107.7 | 129.4 | 0.00 | 0.00 | 0.00 | one-game averages |
| served (plain) | 87.9 | 84.9 | 115.4 | 0.00 | 0.00 | 0.00 | 7 slots on non-players |
| served, market universe only | 109.8 | 110.0 | 142.6 | 0.03 | 0.00 | 0.00 | removing no-props players recovers +22; Jefferson / London / Bijan in 36/36 (8.5 / 8.9 / 11.1) |
| model_pre (plain) | 80.3 | 77.8 | 109.1 | 0.00 | 0.00 | 0.00 | |
| served + house rules | 68.4 | 67.5 | 98.8 | 0.00 | 0.00 | 0.00 | the stack forces the defective QB into every row |
| proj_tourney + house rules | 71.1 | 65.7 | 121.4 | 0.00 | 0.00 | 0.00 | |
| machine book.csv, K97 (Saturday D12800, pre-replacement) | 98.4 | 96.5 | 158.0 | 0.06 | 0.03 | 0.00 | equals the post-mortem's 98.4 |
| entered after Sunday replacements, 97 rows (post-mortem) | 105.0 | – | 156.2 | – | 1 row | – | |
| top-mean counterfactual with 25% cap (post-mortem §13) | 106.3 | – | 183.6 | – | 8 rows | – | Week 2 is excluded from selector tests by rule |

### Week 3, Saturday frame (2026-09-26 15:29Z; cash line 149.5)

| book | mean | median | best | >= cash | >= 150 | >= 194 | note |
|---|---:|---:|---:|---:|---:|---:|---|
| **market** (plain) | **133.1** | 132.8 | 153.3 | 0.08 | 0.06 | 0.00 | pool 208 |
| dk_ppg (plain) | 112.9 | 115.3 | 145.6 | 0.00 | 0.00 | 0.00 | |
| served (plain) | 134.3 | 132.2 | 155.5 | 0.08 | 0.08 | 0.00 | Walker and Gibbs 36/36, Schultz 35/36 (6.0) |
| served, market universe only | 134.6 | 132.2 | 155.5 | 0.11 | 0.08 | 0.00 | |
| model_pre (plain) | 109.9 | 108.7 | 129.1 | 0.00 | 0.00 | 0.00 | |
| served + house rules | 141.7 | 141.7 | 181.9 | 0.36 | 0.33 | 0.00 | |
| proj_tourney + house rules | 142.9 | 142.4 | 174.5 | 0.33 | 0.33 | 0.00 | |
| machine book.csv, K144 (entered) | 120.2 | 119.3 | 178.9 | 0.10 | 0.10 | 0.00 | post-mortem: 120.5 / 10.4% |
| machine book.csv, first 36 | 120.7 | 122.8 | 178.9 | 0.08 | 0.08 | 0.00 | |
| top-mean counterfactual, K144 (post-mortem §6.1) | 151.2 | – | 202.4 | 0.50 | – | – | same pool |

### Week 3, Sunday T-70 frame (2026-09-27 15:29Z; cash line 149.5)

| book | mean | median | best | >= cash | >= 150 | >= 194 | note |
|---|---:|---:|---:|---:|---:|---:|---|
| **market** (plain) | **152.6** | 153.3 | 174.8 | 0.61 | 0.58 | 0.00 | pool 221; Sunday props knew Mason Taylor / Mitchell out |
| dk_ppg (plain) | 112.9 | 115.3 | 145.6 | 0.00 | 0.00 | 0.00 | identical to Saturday (same season averages) |
| served (plain) | 136.8 | 134.4 | 160.8 | 0.17 | 0.14 | 0.00 | 30 distinct players, overlap 5.2 |
| served, market universe only | 136.8 | 134.4 | 160.8 | 0.17 | 0.14 | 0.00 | identical book |
| model_pre (plain) | 109.9 | 108.7 | 129.1 | 0.00 | 0.00 | 0.00 | identical to Saturday: the model did not move |
| served + house rules | 144.2 | 144.9 | 181.9 | 0.42 | 0.39 | 0.00 | |
| proj_tourney + house rules | 143.6 | 145.9 | 174.5 | 0.36 | 0.36 | 0.00 | |
| T-70 machine book.csv, K144 | 120.5 | 119.5 | 203.3 | 0.08 | 0.08 | 0.01 | post-mortem §6.2: 120.5 / row 1 142.1 |
| T-70 machine book.csv, first 36 | 119.6 | 115.7 | 167.6 | 0.03 | 0.03 | 0.00 | |
| Saturday pool re-selected by mean at T-70 (post-mortem §6.2) | 148.3 | – | – | – | – | – | |

## 4. Verdicts

**Does a consensus-projection optimizer beat our entered book?** Yes, on the mean track, in every frame measured,
and the margin is not small: market-plain minus the machine book scored by the same scorer is +12.5 (W1, vs K90;
+9 vs its first 36), +14.1 (W2, vs the Saturday D12800; +7.5 vs the post-replacement entered book), +12.9 (W3
Saturday), +32.1 (W3 T-70). It also beats the field's Millionaire median in W1 (157 vs 141.7) and W3 (133 vs
~127.6 at rank 79,343) and sits at the field mean in W2 (112.5 vs 113-120). A twenty-second solve on the props
numbers, no simulator, no generator, no selector, is a better mean-track book than the one we entered three
weeks running.

**Does it beat our mean-track counterfactual (top-K by projected mean from our own pool)?** Not on the clean
weeks: the top-mean book is 169.7 in W1 (market 157.1) and 151.2 in W3 Saturday (market 133.1). It beats it in W2
(112.5 vs 106.3, but W2's projections are the defective set) and matches it at T-70 (152.6 vs 148.3). So the
ordering on the mean track is: top-mean from our pool >= market-plain > entered book (expected-max) > dk_ppg. The
thing that loses is the expected-max selector, not the projection and not the generator.

**Does the market projection beat our served projection, other things equal (plain rules, same K)?** W1: market
157.1 vs served 132.2 (+25). W2: 112.5 vs 87.9 (+25; defective served set). W3 Saturday: 133.1 vs 134.3 (-1). W3
T-70: 152.6 vs 136.8 (+16). Note the served book has the larger universe (367-439 vs 192-221 rows): the market
book cannot roster a player who has no props number, and that restriction is itself part of why it scores well —
the players without props are the backups, third receivers and punts. `model_pre` (our model before the blend)
is worse than the blend in every frame (130.8 / 80.3 / 109.9 / 109.9), so the market share of the blend is doing the
work; and in W3 the model did not move between Saturday and Sunday while the props did (market 133 -> 153).

**Projection-versus-machinery split (K = 36 in all cells; the machine books are the first 36 rows of their book):**

| frame | (a) served, plain | (b) served + house rules | (c) machine first 36 | (d) market, plain | machinery cost (c) - (b) | projection gap (d) - (a) | house rules (b) - (a) |
|---|---:|---:|---:|---:|---:|---:|---:|
| W1 | 132.2 | 172.1 | 148.1 | 157.1 | -24.0 | +24.9 | +39.9 |
| W2 (defective) | 87.9 | 68.4 | 98.1 | 112.5 | +29.7 | +24.6 | -19.5 |
| W3 Sat | 134.3 | 141.7 | 120.7 | 133.1 | -21.0 | -1.2 | +7.4 |
| W3 T-70 | 136.8 | 144.2 | 119.6 | 152.6 | -24.6 | +15.8 | +7.4 |

Reading: on the three clean frames the generator + simulator + expected-max selector cost 21-25 points per row
relative to a plain optimizer on the same served projection **with** the house construction rules; the served
projection itself is 1-25 points behind the props number; and the house rules (QB+2, bring-back, 49k floor) added
7-40 points on the mean track in the clean frames. The tail is the one place the machinery earns something: the
machine's best rows (224.5, 158.0, 178.9, 203.3) beat the plain books' best (190.1, 161.7, 155.5, 174.8) in three
of four frames, and only `served + house` reached 194+ (five rows in W1). None of the dumb books reaches a
Millionaire top-100 line (208-245).

Diversity caveat: a plain top-K sequential solve with an overlap cap of 7 is a near-duplicate book by design
(rows share 7 players with the first row); its mean is what matters for the satellites, but it is not a portfolio
and would be heavily duplicated in the field (untested here; C5 asks the duplication question).

## 5. Historical co-report (12 of the 36 development slates of 2023-24, every third: weeks 1/4/7/10/13/16)

Frames from `nfl2.pipeline.slate_frame(season, week)` on the k1 panel snapshot; scored on the snapshot's `actual`
(nflverse, post-game). `dk_ppg` does not exist historically; `dk_points_l4` (trailing four weeks, point-in-time)
stands in and is empty in week 1 of a season. The realized field lines were skipped; the shares >= 150 and >= 194
are reported instead.

| slate | rows | market rows | market mean / best / >=150 / >=194 | dk_l4 | served (`proj`) | served + house | served on the market universe |
|---|---:|---:|---|---|---|---|---|
| 2023-w01 | 773 | 216 | 107.4 / 130.5 / 0.00 / 0.00 | n/a | 116.6 / 150.4 / 0.03 / 0.00 | 115.4 / 170.7 / 0.19 / 0.00 | 95.7 / 129.3 |
| 2023-w04 | 577 | 240 | 168.1 / 202.0 / 0.94 / 0.08 | 89.7 / 132.8 | 138.2 / 166.4 / 0.17 / 0.00 | 144.6 / 189.3 / 0.39 / 0.00 | 125.0 / 164.8 |
| 2023-w07 | 486 | 157 | 119.7 / 161.4 / 0.11 / 0.00 | 85.1 / 112.3 | 69.5 / 87.7 / 0.00 / 0.00 | 65.5 / 92.8 / 0.00 / 0.00 | 116.2 / 142.0 |
| 2023-w10 | 483 | 158 | 121.0 / 172.5 / 0.06 / 0.00 | 142.2 / 183.7 | 115.0 / 148.0 / 0.00 / 0.00 | 120.7 / 162.2 / 0.03 / 0.00 | 124.7 / 154.8 |
| 2023-w13 | 483 | 189 | 128.3 / 159.9 / 0.08 / 0.00 | 72.1 / 96.7 | 99.3 / 119.1 / 0.00 / 0.00 | 102.3 / 137.5 / 0.00 / 0.00 | 106.1 / 135.1 |
| 2023-w16 | 433 | 156 | 159.9 / 193.0 / 0.69 / 0.00 | 87.0 / 104.9 | 128.6 / 158.7 / 0.08 / 0.00 | 108.7 / 167.6 / 0.03 / 0.00 | 139.4 / 182.1 |
| 2024-w01 | 700 | 316 | 122.5 / 149.8 / 0.00 / 0.00 | n/a | 111.3 / 140.8 / 0.00 / 0.00 | 98.8 / 115.1 / 0.00 / 0.00 | 111.3 / 140.8 |
| 2024-w04 | 585 | 207 | 159.6 / 189.5 / 0.72 / 0.00 | 102.3 / 131.2 | 93.6 / 142.1 / 0.00 / 0.00 | 120.3 / 165.8 / 0.11 / 0.00 | 113.3 / 148.1 |
| 2024-w07 | 485 | 177 | 135.9 / 151.8 / 0.08 / 0.00 | 98.8 / 115.4 | 115.8 / 139.1 / 0.00 / 0.00 | 127.8 / 157.0 / 0.03 / 0.00 | 129.4 / 156.7 |
| 2024-w10 | 496 | 181 | 115.1 / 141.1 / 0.00 / 0.00 | 105.3 / 133.3 | 86.5 / 112.1 / 0.00 / 0.00 | 88.0 / 116.1 / 0.00 / 0.00 | 90.5 / 118.3 |
| 2024-w13 | 482 | 182 | 134.1 / 157.3 / 0.08 / 0.00 | 118.4 / 145.0 | 121.6 / 140.8 / 0.00 / 0.00 | 116.5 / 139.4 / 0.00 / 0.00 | 133.9 / 145.6 |
| 2024-w16 | 532 | 179 | 149.1 / 182.5 / 0.58 / 0.00 | 86.1 / 107.6 | 115.7 / 148.8 / 0.00 / 0.00 | 117.9 / 143.0 / 0.00 / 0.00 | 147.7 / 183.0 |
| pooled (12 x 36 rows) | | | **135.1** / mean-best 165.9 / 0.28 / 0.007 | 98.7 / 126.3 / 0.03 / 0 (10 slates) | 109.3 / 137.8 / 0.02 / 0 | 110.5 / 146.4 / 0.07 / 0 | 119.4 (market wins 10 of 12) |

Market beats served (`proj`) in 11 of 12 slates by 25.8 points per row on average; house rules add +1.2 on
average (7 of 12). But the historical `served` column is **not the same object as the live served projection**,
which is the anomaly flagged during the run (pool 585 vs 207-264 for the market book, served means near 90):

- In the k1 snapshot, `proj` for every skill player at or under 4,000 is the **p90 punt valuation**, not the mean
  (2024-w04: Joe Milton, a 4,000 backup QB, `proj` 25.1 with `model_points_pre` 0.01 and actual 0; Colby Parkinson
  23.0 against a market 7.6; 2023-w07: Tyler Higbee 20.0 vs model 8.9, Allen Robinson 19.4 vs 7.9, Tommy DeVito
  17.7 vs 1.1). In the live frames that valuation lives in `proj_tourney` and `proj` is clean; historically it was
  written into `proj`. A plain "top-K by `proj`" book historically is therefore the tournament objective and fills
  three or four slots with p90-valued punts, which is exactly what the Week-3 post-mortem measured as the punt rule's
  cost (average tournament value 8.9 against 2.3 realized).
- The historical universe also keeps salary-listed inactive players (773 rows in a week-1 slate), some with
  material `proj`.
- Restricting the same served objective to the market universe (players with a props number, which removes almost
  all sub-4,000 rows) recovers most of it: 2023-w07 69.5 -> 116.2, 2024-w04 93.6 -> 113.3, 2024-w16 115.7 -> 147.7; pooled 109.3 -> 119.4,
  and the market book still wins 10 of the 12 slates, by about 16 per row instead of 26. That residual 16 is the
  cleaner historical estimate of the projection gap (same universe, same rules, same K); the live clean frames say
  +25 / -1 / +16.
- A rerun of the historical served book on `mean_projection` (which exists in the snapshot and should be the clean
  mean) was staged (`hist_books.py served_mean`) but not run inside the time window; until it runs, the historical
  served-vs-market gap of 25.8 is an upper bound that mixes projection quality with the punt valuation. The market
  book's absolute level (135 pooled; 168 / 160 / 160 / 149 on four slates) is unaffected by the anomaly.

## 6. Immediate actions

1. **Build the market-only plain book every Sunday as a shadow and as the mean-track fallback** (pre-lock inputs
   only, one solver, twenty seconds; `B6/live_books.py` is the recipe). Confidence high that it costs nothing and
   moderate-high (4 of 4 frames, including the defective week) that it beats the expected-max book on the mean
   track. It does not replace the pool-based top-mean selection, which beat it on both clean weeks.
2. **Keep the house construction rules when selecting by mean.** On the three clean frames the stack + bring-back +
   floor added +40 / +7 / +7 per row to a plain served-projection book. Low-moderate confidence (three frames; the
   historical read is +1.2 on a contaminated column). This is the B5 question answered from the other side: the
   mandate is not what costs mean points; expected-max is.
3. **Adopt a market floor / pull for the served projection**: `model_pre` loses to the blend everywhere and the
   Sunday props moved 20 points of book value that the model did not see (W3 T-70). Moderate confidence; already on
   the Week-4 list (post-mortem §10 Q7), this adds the plain-book evidence.
4. **Fix the historical snapshot semantics before any further historical "top-K by projection" read**: verify that
   `mean_projection` in `snap_pitclean_k1` is the un-punted mean, and re-read the six co-report slates on it; the
   107-slate "125 vs 118" mean-track comparison in the Week-3 post-mortem used pool `sel_mean`, so it is probably
   unaffected, but that is unverified.
5. **Do not read Week 2's served books as evidence about projection quality**; they measure the availability
   defect (the served plain book rostered non-players in 7 of 324 slots and the house-rule book forced the
   defective QB into every row).

## 7. Unknowns and limits

- K mismatch: the dumb books are 36 rows; the entered books were 80 / 97 / 144. The machine's first 36 rows are
  reported to bridge it, and the post-mortem counterfactuals are quoted at their own K.
- The market book's advantage is partly universe selection: restricting the served book to the props universe
  changes nothing in W1 / W3 (the served top players all had props) but recovers +22 in W2 and +10 pooled
  historically, so universe is a second-order part of the live gap and a first-order part of the historical one.
- The pool top-mean comparator at K = 36 (`B6/pool_topmean.py`) did not run correctly (the candidates' `players` ids
  did not map to the frame ids; every row scored 0) and is discarded; the post-mortem counterfactuals are quoted
  instead.
- The dumb books are near-duplicates of each other; their field duplication and their finish distribution were
  not measured.
- The scorer treats an undrafted, no-actual player as 0; only Week 2 was affected (7 slots, all non-players).
- Week-1 `dk_ppg` is the prior season's average; Week-2 `dk_ppg` is a one-game number. The dk_ppg book is the
  floor of what a DraftKings-screen optimizer would do, not a fair consensus.
- Historical dk_l4 stands in for dk_ppg and is missing in week 1 of each season (10 of 12 slates).
- Solver: CBC via pulp, single thread; results are deterministic for a given frame, so the tables reproduce.
