# Theme C — The field as a forecaster: are we using ownership the right way round?

Research analyst, 2026-09-29. Read-only on every repository; light compute only (single-threaded pandas/numpy,
BigQuery reads). Scripts and intermediate CSVs in `C/` beside this file (`c1_head_to_head.py`, `c3_sources.py`,
`c3b_within_position.py`, `c4_chalk_core.py`, `c5_duplication.sql` (authoritative; `c5_duplication.py` ran on a 200k-row-capped export and is superseded), outputs `c1_output.txt`, `c3_output.txt`,
`c3b_output.txt`, `c4_output.txt`, `c5_bq_output.csv`, per-slate tables `c1_historical_per_slate.csv`, `c3_per_slate.csv`).
No dollar figures. Nothing here concerns the coming slate.

## Inputs and their information time (read this first)

| input | source | information time |
|---|---|---|
| Realized ownership, 2022–25 | `nfl_raw.contest_ownership`, the one Millionaire contest per week (72 slates; ~146 skill players listed per slate, unlisted = treated as 0%) | **post-settlement (REALIZED, after lock)** |
| Realized ownership, 2026 W1–3 | same table, Millionaire contests 193028206 / 195648007 / 195905122, per-slot rows SUMMED per player | **post-settlement (REALIZED)** |
| Our historical projection | `nfl_predictions.slate_player_features`, panel `20260811-pitclean-e80-k1-a12ab31` (research_eligible, 525 skill players per slate); `actual` = realized DK points | point-in-time replay (features from weeks < W); the replay's code, not the live path |
| Our 2026 projection | the build frames: W1 `composite-20260913t1550z-t70` (T-70), W2 `vetted-20260920t1410z-d3200` (Sunday build), W3 `composite-20260927t1550z-d800` (T-70); cross-checked against the last full pre-lock `player_projections` generation (W1 09-08 14:33Z, W2 09-20 16:02Z, W3 09-27 16:03Z) | pre-lock, at the build stamp |
| Lag ownership model | lab `results/l05_sets/lag/` (36 slates 2023–24) | pre-lock (inputs weeks W-1..W-3, i.e. Tuesday) |
| LineStar projected ownership | `~/.cache/linestar-l15/` (L15's pull of LineStar's archive) | **unknown hour; not provably pre-lock** (L15's own caveat) |
| LAG+LineStar blend | lab `results/l15_sets/blend_pct/` | inherits the LineStar caveat |
| own_shadow naive / booster, 2026 W1 | `nfl_predictions.own_shadow`, last batch 2026-09-10 16:57Z | Thursday pre-lock (only W1 was stored; W2/W3 have no rows) |
| Our pools/books | W3 `~/week3-sunday/postmortem/cands_scored.pkl` (12,559) + `our_book.pkl` (144); W1 the K90 scoring subset `learned-K90-…/candidate_scores.csv` (800 of 3,200) + our 57 Millionaire entries; W2 the Thursday rehearsal D6400 pool as a proxy (the Sunday 12,555 pool is not on this host) | pre-lock construction; scored on realized points |
| Field lineups | `nfl_raw.contest_entries`, three Millionaires (831,028 / 172,692 / 161,682 entries) | post-settlement |

Millionaire lines derived from the standings (rank ceiling): cash = top 20% (W1 166.4, W2 138.0, W3 149.3 — matches
the post-mortems' 138 / 149.5); top 1% 209.0 / 179.8 / 188.2; top 100 244.8 / 203.5 / 208.3; field mean 142.1 / 115.6 / 128.5.

---

## C1. Head to head: the field's ten most-owned skill players vs our ten highest-projected

**Historical, 72 Millionaire slates 2022–25** (skill = QB/RB/WR/TE; realized points = snapshot `actual`; the two
top-10 sets overlap by only 1.6 players on average):

| | field top-10 (by realized ownership) | our top-10 (by PIT projection) | paired diff | slates the field wins |
|---|---:|---:|---:|---:|
| all 72 | 17.41 pts/player | **18.86** | −1.45 (se 0.52, t −2.8) | 26 / 72 |
| 2022 | 17.09 | 19.62 | −2.54 | 4 / 18 |
| 2023 | 18.61 | 19.58 | −0.97 | 9 / 18 |
| 2024 | 16.42 | 18.43 | −2.01 | 6 / 18 |
| 2025 | 17.51 | 17.80 | −0.29 | 7 / 18 |

Same position (top-k by ownership vs top-k by projection; k = QB 3, RB 5, WR 5, TE 3):

| position | field | ours | diff | field wins |
|---|---:|---:|---:|---:|
| QB | 20.55 | **22.22** | −1.67 | 27 / 72 (2 ties) |
| RB | **17.90** | 15.91 | +1.99 | **48 / 72** |
| WR | **16.89** | 14.43 | +2.46 | **50 / 72** |
| TE | **11.46** | 9.59 | +1.87 | **48 / 72** |

So the aggregate "we win" is a QB effect (our top-3 QBs are the field's too, and cheap QBs the field likes score
less); **at RB, WR and TE the crowd's top choices out-score our top projections by about 2 points per player in two of
every three slates.** Players in both top-10s average 21.7; field-only 16.6; ours-only 18.3 (n 605 each).

Within-slate rank correlation of realized points with the two rankings, listed players only (the fair comparison —
the "all snapshot players" version, ρ own 0.77 vs proj 0.56, is inflated because realized ownership is ~0 for the
listed-inactive rows, i.e. it carries post-lock availability): **ρ(own) 0.437 vs ρ(proj) 0.414** — near parity, the
field slightly ahead in every season (0.45/0.45/0.47/0.38 vs 0.46/0.43/0.45/0.32).

**2026 W1–3** (frame projection at build; served-table cross-check gives the same sets):

| week | field top-10 | our top-10 | ρ own (listed) | ρ proj (listed) | QB f/o | RB f/o | WR f/o | TE f/o |
|---|---:|---:|---:|---:|---|---|---|---|
| 1 | 17.19 | **21.69** | 0.68 | 0.69 | 19.5 / **22.9** | 19.6 / **24.9** | 19.2 / **23.1** | 7.9 / **11.6** |
| 2 | **17.33** | 16.13 | 0.62 | 0.66 | **21.5** / 18.1 | **14.6** / 13.9 | 16.2 / **25.1** | **15.1** / 10.1 |
| 3 | 21.36 | **22.36** | 0.56 | 0.69 | 21.4 / **24.1** | 22.4 / **23.1** | 22.1 / **24.2** | 8.2 / **12.4** |

Reading: on the three live slates our top-projected set beat the chalk twice (W1, W3) and lost W2 (the defect
week), and our projection out-ranked realized ownership on listed players every week — the reverse of the
historical RB/WR/TE pattern. Three slates cannot separate "the availability repairs fixed it" from luck; the
historical read (72 slates) is the one to weight. **Who forecasts better at the top: at RB/WR/TE the crowd, by ~2
points per player (high confidence, 72 slates); at QB us; overall as a ranker, parity.** Consistent with the
outside-the-box review §2.4 (excess ownership predicts the residual, ρ +0.17) and the winners study §2 (field
ownership informative, partial +0.16; skilled users' deviations from it carry nothing, +0.05).

Unknowns: the ownership file lists only ~146 skill players per slate (below-threshold ownership is unobserved); the
historical projection is the replay's, not the live path; per-position k is a choice (results are stable at k=3/5).

## C2. The field-implied projection

**Answered by the winners study** (`origin/review/winners-study-20260929:reports/2026-09-29-winners-study-and-consistency.md`),
cited, not recomputed: §2 — the field's ownership is informative given our projection (+0.16, t 3.9) while skilled
users' over/under-weights are not (+0.05, t 1.1); within the high-projection band the middle of the ownership range
does best and the least-owned fifth worst. §4.1 — an ownership term INSIDE the capped optimizer objective
(proj + λ × own%) lifts the 36-row book from +2.1 to **+6.1 points over the field at λ 0.20 with the LAG+LineStar
blend** (paired +0.19 sd [+0.06, +0.31], 26/10 slates, both seasons); ceiling with realized ownership +8.5–9.5,
replicated on the 2022 holdout; caveat: LineStar historical not provably pre-lock.

Light supplement (`c1_head_to_head.py`, fit 2022–24, test 2025, listed skill players, n 2,292): MAE ours 6.66 |
ours recalibrated 6.63 | ownership-implied (log-own + salary + position) **5.79** | ours + log-own 5.76 | 50/50 blend
5.93. In the joint model the coefficient on our projection collapses to 0.18: **realized ownership subsumes the
projection**, and part of that is post-lock availability (on the whole snapshot the gap widens to 5.81 vs 2.39 only
because unlisted/inactive rows have both 0% and 0 points — leakage, not forecasting). **These are REALIZED-ownership
upper bounds. The live version must use a pre-lock forecast; C3 measures how good those are.**

## C3. Which pre-lock ownership source is closest to the realized top-15, and when

**36 lab slates 2023–24** (skill players in the oracle file, ~500 per slate; hits = overlap with the realized top-k;
LineStar's top-k is taken among the 34% of players it covers, which include essentially all of the realized top-15):

| source (information time) | top-5 | top-10 | **top-15** | 2023 / 2024 top-15 | level at the realized top-15 (mean predicted %, realized 21.2%) |
|---|---:|---:|---:|---|---:|
| LAG model (Tuesday) | 1.11 (22%) | 3.25 (32%) | **6.00 / 15 (40%)** | 5.33 / 6.67 | 7.2% |
| LAG+LineStar blend (LineStar hour unknown) | 2.61 (52%) | 5.92 (59%) | **9.47 / 15 (63%)** | 9.17 / 9.78 | 12.7% |
| LineStar alone (hour unknown) | 2.58 (52%) | 6.11 (61%) | **9.53 / 15 (64%)** | 9.22 / 9.83 | 18.2% |
| our projection (rank) | 0.50 | 1.72 | 3.47 / 15 (23%) | | |
| value = proj / salary | 0.06 | 0.39 | 1.00 / 15 (7%) | | |

Per position (k = QB 3, RB 5, WR 5, TE 3): LAG 1.31 / 2.33 / 1.61 / 1.03; blend 1.92 / 3.81 / 2.89 / 1.69; LineStar
1.97 / 3.81 / 2.94 / 1.86. Paired blend vs LAG at the top-15: **34 better, 1 worse, 1 tie.** This reproduces L15's
numbers (LAG 5.3/6.7, blend 9.2/9.8) and adds: the vendor is also the only source with a roughly right LEVEL at the
top (18% vs 21% realized; the lag model is 3× too flat, the booster's known failure too).

**By capture hour: cannot be answered from what exists.** The L15 cache has no timestamp; LineStar's archive may be
its final (post-lock) number. The only timed captures are production's live LineStar capture (built 09-29, not yet
graded) and, from the fade side, own_shadow (Thursday). Until a timed capture is graded, treat 9.5/15 as an UPPER
bound for LineStar and 6/15 (LAG) as the floor of a provably pre-lock source.

**2026 W1, the stored booster/naive** (`own_shadow`, Thursday 09-10 16:57Z, vs realized Millionaire ownership):
naive `pred_own` Spearman −0.16 overall, within position +0.07 / +0.10 / −0.38 / −0.06 (QB/RB/WR/TE), DST +0.76,
top-15 hits 0/15; booster +0.65 overall, within position +0.71 / +0.78 / +0.78 / +0.80, top-15 hits 3/15. That matches
the 09-21 first read. **But the same `naive_ownership` formula on the T-70 build frame gives +0.82 overall, within
position +0.82 / +0.91 / +0.92 / +0.90, and 8/15 top-15 hits**; Spearman between the Thursday and the T-70 naive
inputs is 0.01. The Thursday input was wrecked by the QB-availability defect (Wentz 17.8%, Knight 9.9%, Keenum 8.9%,
Taylor 7.8%, Rattler 6.9% predicted — $4k backups), not by the formula. Our plain projection is itself a strong
within-position ownership ranker in all three weeks (ρ 0.83–0.95), but a poor top-15 LISTER (2–4 of 15) because the
realized top-15 are mid-salary value plays (mean salary $6.3–6.4k, median projection rank 30–36). W2/W3 naive(frame):
within position 0.87–0.94, top-15 hits 6 and 5. No booster or LineStar values were stored for W2/W3.

## C4. The chalk-core shape (≤2 players under 5%, ≥1 at 20%+) in our pools and books

All shares use REALIZED Millionaire ownership (post-lock); "core_sk" counts sub-5% skill players only; "strict" =
≤1 under 5% and ≥2 at 20%+. Cash = top 20%.

**The field itself** (all nine slots): chalk-core share 51.9% / 50.4% / 54.7% (W1/W2/W3; the winner-anatomy's
59–68% used a different ownership aggregation); chalk-core mean 146.4 vs 137.5, 118.8 vs 112.3, 132.2 vs 124.0;
cash share 24.6% vs 15.0%, 24.3% vs 15.7%, 24.5% vs 14.6%.

| ours | chalk-core share | realized mean core vs rest | cash share core vs rest | top-1% line | projection core vs rest |
|---|---:|---|---|---|---|
| W3 Sunday D12800 pool (12,559) | **8.0%** (core_sk 9.7%, strict 0.8%) | 132.3 vs 119.4 (**+12.9**) | 31.2% vs 10.7% | 1.49% vs 0.30% | 123.0 vs 117.6 |
| … lev batch (2,560) | 6.0% | 163.1 vs 135.7 (+27) | 85% vs 22% | 4.6% vs 0.7% | 129.4 vs 123.8 |
| … boom batch (9,999) | 8.5% | 126.8 vs 115.1 (+12) | 22% vs 8% | 0.9% vs 0.2% | 121.9 vs 116.0 |
| W3 entered book (144) | **29.2%** (42) | 125.1 vs 118.1 (+7.0) | 19.0% vs 5.9% | 0 / 0 | 126.9 vs 124.2 |
| W1 K90 scoring subset (800 of 3,200) | 31.8% | 150.3 vs 135.5 (+14.8) | 26.8% vs 13.0% | 0.39% vs 1.10% (reversed) | 126.8 vs 117.5 |
| W1 entered Millionaire rows (57) | 40.4% (23) | 143.5 vs **150.0** (−6.5) | 26.1% vs 20.6% | 0 / 0 | — |
| W2 Sunday pool (12,555) | 7.2% (winner-anatomy report; not on this host) | — | — | — | — |
| W2 Thursday rehearsal pool, proxy (6,400) | 3.2% | 106.1 vs 90.1 (+16) | 12.5% vs 3.8% | 0 / 0.06% | 121.4 vs 123.0 |

Reading: **our pools produce the shape ~3–8% of the time against the field's ~52%; the entered books 29–40%.** Where
it occurs it scores +7 to +15 per row and doubles-to-triples the cash rate — but about a third of that is projection
(core rows project +2.7 to +9 higher), the rest is the ownership information of C1/C2, and it is measured on REALIZED
ownership. The one place it reversed is the W1 book mean (n 23 vs 34) and the W1 tail line. Producing the shape on
purpose needs a pre-lock label: L05 (lag labels) landed in cell C — predictor is the bottleneck, sleeve not
flip-eligible; the L07 blend-label run is frozen and pending; the winners study §4.1 reaches the same effect through the
objective term rather than a shape constraint. Confidence: medium on the size (three weeks, one full Sunday pool),
high on the direction (agrees with L05's oracle arm, the field tables above and the 2026-09-22 anatomy).

## C5. Duplication in the three 2026 Millionaires

| | W1 | W2 | W3 |
|---|---:|---:|---:|
| entries / distinct lineups | 831,028 / 773,891 | 172,692 / 166,295 | 161,682 / 155,624 |
| entries that are unique | **89.8%** | **94.3%** | **94.1%** |
| max copies of one lineup | 346 | 150 | 69 |
| top 10: duplicated entries | 2 (rank 5 held twice) | 0 | 2 (rank 5 held twice) |
| top 100: duplicated entries / distinct | 15 / 82 | 2 / 89 | 2 / 89 |
| top 1000: duplicated entries / distinct | 123 / 825 | 87 / 845 | 126 / 824 |
| winner unique? | yes | yes | yes |
| our entries: duplicated | 57 entries: 2 lineups also held by others (7 extra copies; one of ours existed 7× in the field); best rank 34,838 | 1, unique | 1, unique |
| expected prize share per entry (mean 1/copies): top-10 / top-100 / top-1000 / top-1% / cash band | 0.90 / 0.91 / 0.91 / 0.90 / 0.91 | 1.00 / 0.99 / 0.94 / 0.93 / 0.94 | 0.90 / 0.99 / 0.92 / 0.92 / 0.93 |

**Distribution by ownership sum** (entry-weighted deciles of realized own_sum): deciles 1–8 are 93–98% unique in every
week; decile 9 is 83% / 90% / 91% unique; **decile 10 (own_sum > 165) is 57% / 78% / 73% unique** with mean copies 6.6 /
2.0 / 2.6. By number of sub-5% players: zero sub-5% → 31% / 18% / 20% of entries duplicated (mean copies 5.8 / 2.1 /
2.2); one → 13% / 9% / 7%; two → 7% / 4% / 3%; three or more → 2–5%. Chalk-core lineups are 84.5% / 91.6% / 91.2%
unique vs 95.4% / 97.1% / 97.7% for the rest. Yet zero-sub-5% entries still score the highest mean (151.7 / 122.1 /
134.5 vs 147.1 / 118.8 / 130.6 with one): the duplication penalty (≈10% prize share) is smaller than the score gain.

**Cost of a duplicate at each line:** a duplicated lineup at any line splits its prize with, on average, 1.2–1.5 other
copies in the top 1,000 and up to 2.4 in the cash band — i.e. an expected 7–10% dilution per entry at the lines we
reach; the top-100 dilution is 1–9%. It is not a lever: 90–94% of the field is unique, our rows are unique, and the
one Week-1 lineup of ours that existed 7 times was a chalk optimizer output, not a loss. R12 can be marked measured.

---

## Immediate actions (this week, no new model)

1. **Do not re-arm the chalk fade; keep ownership as a POSITIVE input.** Evidence: C1 (the crowd's top RB/WR/TE
   out-score our top projections in 48–50 of 72 slates), C2/winners study §2 and §4.1, §2.4. The
   `proj_tourney = base − 25·own_est` form is the wrong sign; it has been off all season anyway (fade-never-fired
   report). Confidence: high.
2. **If an ownership term goes into the capped objective (winners study §4.1, λ 0.20, blend), feed it the T-70
   frame's inputs, never the Thursday pool's.** C3 shows the same naive formula is uninformative on Thursday's frame
   (ρ −0.16) and strong on the T-70 frame (ρ +0.82, 8/15 top-15) because of the availability defect. Whatever source
   is blended, compute it after the availability repairs. Confidence: high on the mechanism, medium on the lift (the
   lift number is the winners study's, on 36 slates, with the LineStar caveat).
3. **Grade the timed LineStar capture against the realized top-15 the Monday after each slate** (hit rate at
   top-5/10/15 and level at the top, per position, as in `c3_sources.py`) and compare to the untimed 9.5/15. That is
   the only way to learn the capture-hour answer C3 asks for. Also store `own_shadow` every week (W2/W3 have no rows).
   Confidence: high that it is needed; zero cost.
4. **In selection, prefer rows with ≤2 predicted sub-5% players and ≥1 predicted 20%+ using the blend labels only as a
   tie-breaker, not a constraint,** until L07 reads. C4: +7 to +15 per row and 2–3× the cash rate on realized labels; but
   the pre-lock version failed with lag labels (L05 cell C) and is untested with blend labels. Confidence: low-medium.
5. **Ignore duplication.** C5: our rows are unique, the field is 90–94% unique, and the dilution at every line is
   ≤10%. Do not add uniqueness constraints; keeping one sub-5% player per row would cut duplication risk but costs ~4
   points of mean in the field data. Confidence: high.
6. **Log the C1 per-position head-to-head weekly** (field top-k vs our top-k realized points). Historically our top
   RB/WR/TE projections trail the crowd's picks by ~2 points per player; in 2026 the sign flipped after the availability
   repairs (ours won W1 and W3). Three slates decide nothing; six to eight will. No projection change now.

## Confidence and unknowns, summarized

- High: C1 historical (72 slates, paired t −2.8, position split 48–50/72); C3 rankings of sources (replicates L15,
  34-1 paired); C5 (full fields).
- Medium: C4 sizes (one full Sunday pool, an 800-row W1 subset, a Thursday W2 proxy; realized-ownership labels).
- Low: anything about 2026 direction from three slates; the capture-hour question (no timed source exists yet).
- Unknowns: LineStar archive hour; the Week-2 Sunday pool (not on this host); ownership below the Millionaire listing
  threshold (treated as 0%); the historical projection is the replay's code, not the live path; payout ladders (the
  prize-share dilution is expressed as shares, not amounts).
