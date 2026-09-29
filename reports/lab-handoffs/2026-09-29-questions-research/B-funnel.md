# Theme B (B1–B5) and Theme D (D1–D3): where the points go between projection and entry

Research analyst, 2026-09-29. Read-only; light single-threaded pandas plus BigQuery reads. Scripts and raw outputs in
`B/` (`common.py` loaders; `b1_funnel.py`, `b1b_decomp.py`, `b2_b3_d3.py`, `b4_calibration.py`, `b5_stacks.py`,
`d2_late_info.py`; each writes a `.out` beside it; pulled data under `B/data/`). No Week-4 data was read. Salaries are
written in DK salary units ("8.8k"), never as money.

**Anchors taken from existing work, not recomputed:** the winners study (`origin/review/winners-study-20260929`,
`reports/2026-09-29-winners-study-and-consistency.md`): §3.1 entered books vs the field (+0.09 sd W1, −0.47 W2,
−0.46 W3, about 12 points below the field in W2–W3); §2 lineups in the 80th–98th percentile of our projected sum score
about +8 over the field; §6 Sunday re-projection moves active players' projections 0.26 points on average with
identical accuracy (MAE 5.361 vs 5.369) and all of Sunday's value is knowing who is out (W2 error 6.98 → 5.41). The
three post-mortems (W1 09-13/09-14, W2 09-21 §2–§5/§13, W3 09-27 §0–§7/§10–§12), the stack-depth read (09-20), the
generator-batches note (09-22), the pool-quality decomposition (09-22), L11 (09-28) and the HANDOFF availability entries.

**Information time of every input.** Saturday build = the Saturday D12800 run dir (W2 15:30Z Sat, W3 15:34Z Sat; W1 has
no D12800, its Saturday pool is the D3200 built 20:49Z Sat) and its `frame.parquet` projections (Saturday DK pull).
T-70 build = the Sunday D800 run (W1 15:56Z, W2 15:50Z, W3 15:50Z) and its frame (DK pull 15:04Z / 15:49Z / 15:29Z —
note W1 and W3 T-70 frames were pulled BEFORE the 15:30Z inactives). Entered book = the rows actually uploaded (W1 80
distinct rows after the manual swaps, source build 16:04Z Sunday; W2 97 rows from the Saturday build after the 52-row
replacement and the rank-7→1 promotion; W3 144 rows from the Saturday build with the 5 Sunday scratch swaps). Realized =
DraftKings FPTS from the standings files (`nfl_raw.contest_ownership`, max over contests), nflverse `dk_points` for
players nobody drafted, 0 if neither (no player with projection > 3 fell into "neither"). Field = the week's Millionaire
(`nfl_raw.contest_entries`; means and top-1% exact from all entries; projected sums from a 2% random sample plus every
top-1% row). "Cash line" = the Millionaire's 80th percentile (166.4 / 138.0 / 149.3; W3's 149.3 matches the
post-mortem's 149.5). "Punt" = QB/RB/WR/TE at salary ≤ 4.0k; in every frame `proj` equals the blended mean for all
players and `proj_tourney` is the p90-valued number for punts only (verified: 244 of 244 punts lifted, 0 non-punts).
The `lev` batch is solved on `proj_tourney`; `sel_mean` equals the plain projected sum (r = 1.000).

---

## B1. The funnel, one table per week (projected vs realized, so the gap splits into projection error and selection)

"Top-K by mean" = the K highest projected sums with pairwise overlap ≤ 7, K = the entered count (the Week-4 mean-track
rule from post-mortem §11). "Error" = realized − projected for the same rows.

### Week 1 (Saturday D3200 pool of 3,200; entered 80; field 831,028)

| stage | projected | realized | error | n | share ≥ cash |
|---|---:|---:|---:|---:|---:|
| pool top-1 by projected mean | 133.2 | 188.7 | +55.5 | 1 | |
| optimizer best (lev argmax of `proj_tourney`) | 128.1 | 152.8 | +24.7 | 1 | |
| top-80 by mean, overlap ≤ 7 | 130.8 | **172.7** | +42.0 | 80 | 64% |
| pool batch lev | 127.0 | 158.6 | +31.6 | 640 | 35% |
| pool batch boom | 116.4 | 136.7 | +20.3 | 2,560 | 16% |
| pool, all | 118.5 | 141.1 | +22.5 | 3,200 | 19% |
| delivered expected-max book (K90, pre-vetting) | 121.9 | 149.3 | +27.4 | 90 | |
| **entered book** (80, after manual swaps) | 123.2 | **143.5** | +20.2 | 80 | 20% |
| field mean (Millionaire) | 119.5 | 142.1 | +22.5 | | 20% |
| field top 1% | 122.6 | 218.3 | +95.7 | 8,314 | |

### Week 2 (Saturday D12800 pool of 12,555; entered 97; field 172,692) — the availability-defect week

| stage | projected | realized | error | n | share ≥ cash |
|---|---:|---:|---:|---:|---:|
| pool top-1 by projected mean | 148.0 | 53.6 | −94.5 | 1 | |
| optimizer best (lev argmax) | 137.8 | 67.3 | −70.5 | 1 | |
| top-97 by mean | 143.4 | 71.0 | −72.4 | 97 | 0% |
| pool batch lev | 136.7 | 76.7 | −60.0 | 2,560 | 0% |
| pool batch boom | 122.0 | 98.0 | −24.0 | 9,995 | 6% |
| pool, all | 125.0 | 93.7 | −31.4 | 12,555 | 5% |
| delivered expected-max book (K97, pre-vetting) | 132.8 | 98.4 | −34.4 | 97 | |
| **entered book** (97, after replacement + promotion) | 129.4 | **105.0** | −24.5 | 97 | 7% |
| field mean | 123.6 | 115.5 | −8.1 | | 20% |
| field top 1% | 124.5 | 189.0 | +64.4 | 1,729 | |

### Week 3 (Saturday D12800 pool of 12,559; entered 144; field 161,682)

| stage | projected | realized | error | n | share ≥ cash |
|---|---:|---:|---:|---:|---:|
| pool top-1 by projected mean | 133.2 | 127.6 | −5.7 | 1 | |
| optimizer best (lev argmax) | 128.5 | 130.2 | +1.8 | 1 | |
| top-144 by mean | 130.6 | **151.4** | +20.8 | 144 | 51% |
| pool batch lev | 124.1 | 137.4 | +13.3 | 2,560 | 26% |
| pool batch boom | 116.5 | 116.1 | −0.4 | 9,999 | 9% |
| pool, all | 118.1 | 120.4 | +2.4 | 12,559 | 12% |
| delivered expected-max book (K144, pre-vetting) | 125.0 | 120.2 | −4.9 | 144 | |
| **entered book** (144) | 125.0 | **120.5** | −4.5 | 144 | 10% |
| field mean | 122.7 | 128.5 | +5.8 | | 20% |
| field top 1% | 124.9 | 196.0 | +71.1 | 1,620 | |

(W3 entered 120.5 / best 178.9 and W2 entered 105.0 / best 156.2 reproduce the post-mortems exactly; the W1 entered
book here is the 80 rows actually uploaded, 143.5, versus the post-mortem's 146.6 for the K80 delivered book.)

**Where the biggest drop is.** In the two clean weeks the largest drop is the same stage: *from the top-K-by-mean book
to the entered book*: −29.2 (W1) and −31.0 (W3) realized points per row. Only a quarter of that is visible in projected
points (−7.6 and −5.6); the rest is that the expected-max selector's rows realize *below* their projection (+20 / −4.5)
while the top-mean rows realize *above* it (+42 / +21). The residual is not noise spread evenly over the pool; it is
correlated with what the selector prefers. Two pool-wide reads say the same thing (B/b1b_decomp.out): the realized −
projected residual rises with the row's Millionaire-ownership sum (W1 low/mid/high terciles +22.5 / +16.0 / +29.1; W3
−2.4 / +2.6 / +6.9) and is best for 3-punt lev rows (W1 +34, W3 +15) and worst for 4-punt rows and boom rows (W3 −4.9
for zero-punt boom rows). Our projection ranks our own pool well: realized rises faster than projected across pool
quintiles (W1 proj 110.6→127.8 vs realized 130.0→162.5; W3 109.6→125.7 vs 112.2→133.1; correlation +0.40 / +0.32). Week
2 inverts everything (−0.49) because the highest projected rows held non-players (post-mortem §13; this is the same
number).

**Against the field.** In projected points every one of our books sits *above* the field's average lineup (entered
123.2 vs 119.5; 129.4 vs 123.6; 125.0 vs 122.7), yet realized is +1.4 / −10.5 / −8.0 (winners study §3.1: +0.09 / −0.47
/ −0.46 sd). So the "we are below the field" gap is entirely in the residual: our entered rows realize 2 (W1), 16 (W2)
and 10 (W3) points less relative to projection than the field's rows do, while our top-mean rows realize 20 (W1) and 15
(W3) points *more* than the field's. The projection is not the stage that loses; the choice of rows is. The field's
top 1% is only +3 projected points above the field mean (122.6 vs 119.5; 124.9 vs 122.7): our projection does not
identify the top 1%, consistent with "which studs boom is noise" (W1 post-mortem §3.4).

**Who explains the W3 gap (exact player decomposition, entered vs top-144-mean, sum −31.0):** Gibbs (entered 31% vs
top-mean 96%, 41.4 pts) −26.7; Shough (8% vs 54%, 26.8) −12.1; Juwan Johnson (5% vs 47%, 24.3) −10.1; Olave (8% vs 46%)
−8.7; Walker (33% vs 72%) −8.4. W1: Gibbs (28% vs 100%, 37.6) −27.3; Shough (11% vs 99%, 29.2) −25.6; Vele (10% vs 90%)
−15.9; Bijan −12.9; Juwan Johnson −11.3. **Caveat that must travel with the mean track:** the uncapped top-K-mean book is
one core (44 distinct players in W1, 91 in W3; Gibbs in 96–100% of rows; ownership sum 150 / 121 vs the entered 99 /
100). Its +29/+31 is a concentrated bet that hit twice and, on the W2 defect pool, lost by 34. This is the winners
study's §3.2 "the book moves as one"; the armed 50% exposure cap is the answer, and the cost of the cap is unmeasured
here.

**Batches.** lev out-realizes boom in both clean weeks (W1 158.6 vs 136.7; W3 137.4 vs 116.1) and holds the pool's
highest projected means; boom's edge is only the single best row (W1 236.3, W2 197.3, W3 207.1 — all boom; cf. the 09-22
generator-batches note where every W2 top-1% row was boom). On the mean track lev is the batch that matters.

Confidence: high on the direction (two clean weeks, exact reproductions of the post-mortem numbers, W2 explained by the
defect); medium on magnitude (two weeks; the top-mean book's +29/+31 is one core each time). Unknown: the top-mean
book's mean under the 50% exposure cap on these three pools (the lab's L18 replay gives +2 vs the field historically).

---

## B2. Predictable duds in the entered rows

Dud classes, valued at build time (W1 the 16:04Z source frame; W2/W3 the Saturday frame) and checked again on the T-70
frame; a slot counts as a dud only if the player also scored under 5. "Value − realized" uses the number the row was
built on (`proj_tourney` for punts, `proj` otherwise). "Replacement gain" swaps the dud for the best *mean-projected*
same-position player affordable in that row who was not OUT/D at build (a pre-lock choice; realized points of the
replacement minus the dud; same-slot swap, not a re-solve).

| week | class | rows holding | dud slots (<5) | value − realized per holding row | replacement gain per holding row | mean realized, rows with a dud |
|---|---|---:|---:|---:|---:|---:|
| 1 | OUT/D/IR at build or by T-70 frame | 0 | 0 | | | |
| 1 | backup QB (depth ≥ 2) | 1 | 1 | 12.3 | 19.2 | |
| 1 | depth ≥ 3 RB/WR/TE | 2 | 2 | 5.5 | 17.4 | |
| 1 | p90-valued punt (≤ 4.0k skill) | 60 | 29 | 6.7 | 4.8 | 143.5 |
| 2 | OUT/D/IR at build or by T-70 | 0 | 0 | | | |
| 2 | backup QB | 4 | 0 | | | |
| 2 | depth ≥ 3 RB/WR/TE | 42 | 16 | 1.9 | 0.2 | 93.2 |
| 2 | p90-valued punt | 86 | 47 | 7.7 | 3.8 | 100.5 |
| 3 | OUT/D/IR at build or by T-70 | 0 | 0 | | | |
| 3 | backup QB | 1 | 0 | | | |
| 3 | depth ≥ 3 RB/WR/TE | 55 | 37 | 2.5 | 2.9 | 120.0 |
| 3 | p90-valued punt | 111 | 74 | 9.6 | 4.7 | 116.8 |

Sub-1-projection players: none reached an entered row in any week (the 399 boom lineups holding one in W3 never left
the pool; post-mortem §6.4). OUT/Doubtful: none in any entered row at build or at T-70; the replacement and scratch
steps did their job.

Rows holding any predictable dud that scored under 5: **25 of 80 (31%) W1, 43 of 97 (44%) W2, 66 of 144 (46%) W3**.
Their realized mean vs the clean rows: 143.5 vs 143.4 (W1, flat), 99.0 vs 109.7 (W2), 117.0 vs 123.3 (W3). Points lost
to the class alone (replacement gain summed over affected rows, spread over all entered rows): **4.3 / 3.5 / 4.7 per
entered row** (13.8 / 7.9 / 10.3 per affected row). The class is almost entirely the p90-valued punt: a ≤ 4.0k skill
player valued at 16–20 in the objective, projected 7–10 on the mean, scoring under 5. Entered rows by punt count (W3):
0 punts 119.1, 1 punt 119.3, 2 punts 120.8, 3 punts 132.5 — the three-punt rows are the lev rows, whose punts are the
high-mean ones (see B3).

Confidence: high that the class exists and is 3.5–4.7 points per row; medium on the replacement number (a same-slot
swap understates what a re-solve would do and ignores correlation).

---

## B3. Is the p90 punt valuation earning its keep under the MEAN objective?

What the valuation is: for every punt, `proj_tourney` ≈ mean + 1.5 sd (the 09-21 "measured effect of the p90 view"
note: fixed-z offset), so it adds roughly +9 to +10 to every punt regardless of who he is. It changes the *order among
punts* very little and changes the *punt-vs-priced trade-off* a lot: every lev row carries 3–4 punts (W1 3.18, W2 3.21,
W3 3.74 per row).

**Realized points of lev rows by number of punts (Saturday pools; lev rows are built on the valuation):**

| week | 2 punts | 3 punts | 4 punts |
|---|---|---|---|
| 1 | — | n 524, proj 128.3, realized **162.9**, 42% ≥ cash | n 116, proj 121.3, realized **139.2**, 3% |
| 2 (defect) | n 16, realized 60.2 | n 1,987, realized 72.1 | n 557, realized 93.7 |
| 3 | — | n 670, proj 129.1, realized **147.2**, 45% | n 1,890, proj 122.3, realized **133.9**, 19% |

In the clean weeks the fourth punt costs 13–24 realized points and 22–26 points of cash-rate, and it also costs
projected mean (−7), i.e. the optimizer only takes a 4th punt because the valuation says he is worth 15+. Boom rows
(built on plain means, punts only through the simulated worlds) show the opposite gentle slope: W3 0/1/2/3 punts →
111.8 / 115.0 / 119.5 / 125.2, because boom's punts are the ones a world picked.

**The punts themselves, by pre-lock valuation bucket (Saturday `proj_tourney`) → realized:**

| week | valued 8–12 | 12–15 | 15–18 | 18+ |
|---|---|---|---|---|
| 1 | n 132, mean proj 2.3, realized 1.2, P(10+) 3% | n 33, proj 5.3, real 5.5, 24% | n 22, proj 7.0, real 5.3, 18% | n 12, proj 9.8, real 2.0, 8% |
| 2 | n 61, proj 2.7, real 1.8, 3% | n 19, proj 5.2, real 2.4, 0% | n 24, proj 7.4, real 4.7, 8% | n 31, proj 11.0, real 3.6, 6% |
| 3 | n 85, proj 2.1, real 2.0, 2% | n 22, proj 5.1, real 5.3, 32% | n 16, proj 7.5, real 9.9, 38% | n 4, proj 10.2, real 5.1, 0% |

By mean-projection bucket the picture is the same and cleaner: punts projected 8+ realized 6.5 / 4.3 / 9.2 (P(10+)
31% / 11% / 22%); 5–8 → 3.9 / 3.4 / 7.6; 3–5 → 3.9 / 2.0 / 3.1; under 3 → about 0.5–2. So the **mean projection is
roughly unbiased for punts** (lev-exposure-weighted punt slot: mean proj 9.2 / 10.2 / 7.4 vs realized 10.3 / 6.3 /
7.3) while the **valuation overstates every punt slot by 9–14 points** (valuation 18.2 / 20.1 / 16.4): per lev row that
is 25 / 44 / 34 points of objective that does not exist. Rank quality among punts projected ≥ 1: Spearman(valuation,
realized) +0.42 / +0.29 / +0.47 versus Spearman(mean, realized) +0.44 / +0.25 / +0.44 versus market +0.43 / +0.24 /
+0.44 — the valuation ranks punts no better than the mean does. (W2 "18+" bucket includes the backup QBs valued 20–24,
the 399-lineup non-player problem.)

**Counterfactual on lev rows** (each punt with mean projection < 5 swapped for the best mean-projected same-position
player affordable in that row): +0.1 (W1), +3.6 (W2), +2.8 (W3) realized per lev row; 2% / 20% / 39% of rows improved.
That is a lower bound for a plain-mean lev batch, because it does not re-solve.

**On the mean track specifically:** selection is by `proj` (the mean), so the valuation only acts through which rows
exist. The best mean-track book in W3 comes from lev (top-144-mean from lev 152.8 vs from boom 129.9), and its rows
average 3.0 punts — the *high-mean* punts (Juwan Johnson 8.5→24.3, Mayer 7.8→12.2, Hutchinson 9.5→8.5). Whether a lev
batch solved on the plain mean (fewer, better punts, more salary on the 6.5k+ WR/RB the field's winners buy) beats it
cannot be read without a solve; the post-mortem's R5 note (a plain-mean optimizer pool reaches projected mean 133.3 vs
this pool's best-144 at 130.6) says the projected side favours it. Q4b (laptop, Tue) is the right test; expected size
from the reads above: +3 to +4 per lev row from removing the 4th-punt rows, plus whatever the re-solve adds.

**Verdict:** under the mean objective the p90 valuation is not earning its keep: it adds no ranking information over the
mean, it forces a fourth punt into 18–74% of lev rows, and those rows are the worst lev rows in both clean weeks. It
was kept for the best-of-40 tail ("true-deletion tests cost tails"), which the mean track does not use. Confidence:
medium-high (two clean weeks, consistent direction, matches the 09-14 cheap-slots read that sub-8 punts are dead and
8–12 punts carry the tails). Unknown: the re-solved plain-mean lev batch itself.

---

## B4. Points per salary by position × tier: served projection vs realized

**2026 W1–3, served projections** (`nfl_predictions.player_projections`, last pre-lock batch 16:03Z / 16:02Z / 16:03Z
Sunday; realized DK FPTS, 0 if none; main-slate players only). "Bias" = realized − projected; per-1k = points per 1,000
of salary.

| pos | tier | n | played | proj | realized | bias | proj/1k | real/1k | played-only bias |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QB | < 5.5k | 159 | 28% | 5.1 | 4.1 | −1.0 | 1.20 | 0.95 | +1.2 |
| QB | 5.5–6.5k | 25 | 100% | 19.6 | 17.1 | **−2.5** | 3.32 | 2.90 | −2.5 |
| QB | 6.5–7.5k | 12 | 100% | 20.9 | 21.5 | +0.6 | 3.09 | 3.18 | +0.6 |
| QB | 7.5k+ | 2 | 100% | 25.2 | 20.5 | −4.8 | 3.26 | 2.64 | −4.8 |
| RB | 4–5.5k | 114 | 79% | 5.5 | 4.5 | −1.1 | 1.18 | 0.95 | −0.7 |
| RB | 5.5–6.5k | 32 | 100% | 13.0 | 13.6 | +0.6 | 2.21 | 2.31 | +0.6 |
| RB | 6.5–7.5k | 22 | 100% | 16.1 | 14.9 | −1.2 | 2.34 | 2.16 | −1.2 |
| RB | 7.5k+ | 8 | 100% | 20.2 | 24.6 | **+4.4** | 2.51 | 3.06 | +4.4 |
| WR | 4–5.5k | 94 | 91% | 8.7 | 8.4 | −0.3 | 1.85 | 1.79 | +0.1 |
| WR | 5.5–6.5k | 39 | 97% | 12.7 | 12.8 | 0.0 | 2.14 | 2.15 | +0.3 |
| WR | 6.5–7.5k | 16 | 94% | 13.1 | 18.5 | **+5.3** | 1.92 | 2.71 | +5.7 |
| WR | 7.5k+ | 10 | 100% | 19.4 | 21.6 | **+2.2** | 2.46 | 2.74 | +2.2 |
| TE | 4–5.5k | 23 | 91% | 10.1 | 9.3 | −0.8 | 2.21 | 2.03 | +0.1 |
| TE | 5.5k+ | 6 | 83% | 12.3 | 15.8 | +3.5 | 1.88 | 2.42 | +6.0 |
| DST | 3.6k+ | 6 | 100% | 8.8 | 4.0 | −4.8 | 2.38 | 1.08 | −4.8 |

Top-8 projected per position each week (proj → realized): **WR 15.9→21.6, 17.7→21.7, 17.7→21.4** (under in all three
weeks); RB 17.7→22.7, 17.2→11.4, 18.9→21.2; QB 21.1→20.4, 21.4→17.7, 21.4→21.9; TE 10.0→11.5, 11.3→10.9, 12.3→11.9.
Per-week bias among players projected ≥ 5: QB −3.6 / −2.9 / +1.1; WR +0.2 / −0.8 / +0.3; RB +0.7 / −2.4 / −0.8; TE
+1.8 / −1.8 / +2.6.

**2023–25 (54 slates, replay projections of the 107-slate panel `20260811-pitclean-e80-k1-a12ab31`, point-in-time; not
the live served path):**

| pos | tier | n | bias | proj/1k | real/1k |
|---|---|---:|---:|---:|---:|
| QB | 5.5–6.5k | 468 | −0.8 | 2.82 | 2.68 |
| QB | 6.5–7.5k | 204 | **−1.8** | 2.84 | 2.57 |
| QB | 7.5k+ | 101 | +0.4 | 2.78 | 2.83 |
| RB | 4–5.5k / 5.5–6.5k / 6.5–7.5k / 7.5k+ | 1,740 / 605 / 342 / 204 | −0.1 / +0.3 / +0.2 / −0.6 | 1.16 / 1.97 / 2.11 / 2.18 | 1.14 / 2.01 / 2.15 / 2.11 |
| WR | 4–5.5k / 5.5–6.5k / 6.5–7.5k / 7.5k+ | 1,194 / 635 / 350 / 273 | −0.1 / +0.3 / −0.6 / **+0.6** | 1.82 / 2.02 / 2.07 / 2.11 | 1.80 / 2.07 / 1.98 / 2.19 |
| TE | 4–5.5k / 5.5k+ | 332 / 143 | −0.4 / −0.1 | 2.10 / 2.10 | 2.01 / 2.08 |
| DST | all tiers | 1,194 | −0.6 / +0.1 / +0.1 | 2.3 | 2.05–2.38 |

**Answer.** Yes in direction, modest in size historically, large in 2026 on tiny samples. Expensive QBs are
over-projected by 0.8–1.8 points (3–7%) historically and by 2.5 in the 5.5–6.5k tier this season; stud WRs (7.5k+)
are under-projected by +0.6 historically (real/1k 2.19, the best of any priced tier) and by +2 to +5 this season
(n = 26 across the two stud tiers); stud RBs are flat historically (2.11–2.15/1k) and +4.4 this season on n = 8. Points
per salary rise with price at RB and WR (1.14 → 2.11; 1.80 → 2.19) and are flat-to-falling at QB above 5.5k. So the
salary allocation gap versus the winners (post-mortem §7: QB +0.8k, TE +0.5k, WR −1.3k, RB −0.7k) is consistent with
the projection's tilt — but the historical tilt is worth about 1 point per slot, not the 5 points this season shows.
Two structural items in the same table: sub-5.5k QBs have a 28% play rate (the backup contract; the Saturday batch had
them at 7.5 vs 4.1 realized, the T-70 batch after the QB gate 5.1) and DST above 3.6k is −4.8 (n = 6, DST projections
carry no rank skill per the 09-22 decomposition). Confidence: high on the historical direction (n in the hundreds),
low on the 2026 magnitudes (8–26 players per stud tier). Unknown: whether the 2026 stud under-projection is a
one-season-window artefact (the `_l4` windows restart each season; W2 post-mortem §9) — it would be worth re-reading
after Week 6.

---

## B5. The stack mandate (QB+2 same-team WR/TE + bring-back in every row) on the MEAN track

Our pools carry the mandate in 100% of rows, so inside the pool only depth 2 vs 3 and distinct-game count vary. The
field is the only place the mandate itself can be measured. Definitions as in the post-mortems: depth = same-team WR/TE
with the QB; bring-back = a skill player from the opponent; "cash" = share ≥ the Millionaire's 80th percentile.
Field numbers are from the 2% random sample (16,422 / 3,446 / 3,212 rows) and every top-1% row.

**Field, realized mean and cash share by construction:**

| week | feature | field share | realized mean | cash | top-1% lift |
|---|---|---:|---:|---:|---:|
| 1 | depth 0 / 1 / 2 / 3 | 19% / 53% / 26% / 2% | 139.5 / 140.9 / 143.1 / 145.3 | 16% / 18% / 22% / 27% | 0.53 / 0.84 / 1.46 / 4.13 |
| 1 | bring-back 0 / 1 | 56% / 44% | 140.3 / 142.6 | 17% / 22% | 0.62 / 1.49 |
| 1 | games 4 / 5 / 6 / 7 | 10% / 27% / 35% / 21% | 143.5 / 142.5 / 141.5 / 138.8 | 23% / 21% / 19% / 15% | 1.76 / 1.27 / 0.80 / 0.64 |
| 2 | depth 0 / 1 / 2 / 3 | 16% / 58% / 25% / 1% | 113.0 / 114.5 / 116.5 / 114.2 | 17% / 18% / 24% / 24% | 0.73 / 0.98 / 1.22 / 1.17 |
| 2 | bring-back 0 / 1 | 58% / 42% | 114.1 / 115.6 | 19% / 21% | 1.03 / 0.96 |
| 2 | games 4 / 5 / 6 / 7 | 6% / 23% / 37% / 25% | 113.5 / 114.2 / 114.7 / 115.5 | 21% / 18% / 19% / 20% | 0.75 / 1.00 / 1.02 / 1.02 |
| 3 | depth 0 / 1 / 2 / 3 | 17% / 52% / 29% / 2% | 124.3 / 127.3 / 129.8 / 135.3 | 13% / 18% / 24% / 29% | 0.16 / 0.50 / 2.22 / 3.68 |
| 3 | bring-back 0 / 1 | 61% / 39% | 127.0 / 128.8 | 18% / 21% | 0.57 / 1.67 |
| 3 | games 4 / 5 / 6 / 7 | 7% / 24% / 36% / 24% | 130.2 / 128.7 / 126.7 / 127.1 | 23% / 22% / 18% / 17% | 2.50 / 1.57 / 0.85 / 0.51 |

Field rows that satisfy *our* mandate (depth ≥ 2 and a bring-back): 15.8% / 13.8% / 16.0% of the field; realized
145.3 vs 140.6 (W1), 117.3 vs 114.3 (W2), 131.4 vs 127.0 (W3); cash 26–27% vs 18% every week; share of the top 1%
36.6% / 16.7% / 51.8%. Controlling for the projection (field rows in the top projected quintile): depth 2 vs 1 realized
154.8 vs 148.4 (W1), 113.2 vs 113.8 (W2), 143.4 vs 136.6 (W3); by distinct games 4 / 5 / 6 / 7 → 157.7 / 152.2 /
148.7 / 143.5 (W1), 105.3 / 112.1 / 114.3 / 117.8 (W2), 147.1 / 138.0 / 136.8 / 136.4 (W3).

**Inside our pools** (Saturday, all rows already mandated): depth 3 vs 2 realized 156.3 vs 140.6 (W1, n 92), 97.4 vs
93.6 (W2), no depth-3 rows in W3 (cap 4 per game); two bring-backs vs one 154.3 vs 139.3 (W1), 91.5 vs 93.8 (W2). A
top-K-mean book restricted to depth 2 loses almost nothing (W1 170.6 vs 172.7); restricted to ≥ 5 games it is flat
(W1 171.1, W3 151.1 vs 151.4); restricted to ≤ 4 games it is worse only because the pool's high-mean rows are not there
(W3 142.1 at projected 128.5).

**Answer.** On the mean track the mandate does not cost points; it earns them. In all three weeks the field rows that
look like ours score 3–5 points more than the rest and cash 8–9 points more often, and given the projection, two-deep
stacks beat one-deep in the two clean weeks (+6 to +7). The "5.4 distinct games vs our 3.7" comparison (W2 post-mortem
§2) is a field average, not a winners' edge: with the projection held fixed, *fewer* games realize more in W1 and W3
(4 games > 5 > 6 > 7) and the top-1% lift falls monotonically with game count in those weeks; W2 is the exception and
flat. The tail-track closure (W1 post-mortem §3.3: deeper stacks lower realized exceedance; the 09-20 stack-depth read:
depth 3 −3 on the mean over 107 slates, inconclusive) is about depth 3+, not about the QB+2 + bring-back floor, and this
season's fields (W1 §C, W3 top-100 79% QB+2 / 75% bring-back vs 32% / 41% field) side with the floor. What the mandate
does cost is *shape diversity*: every row has 4 players from one game, so the book moves together; that is a
concentration cost, not a mean cost. Satellite-line (p91–p99) tickets by construction were not measured here (needs
the per-contest ladders; the winners study §5 has the book-level rates). Confidence: medium-high on "no mean cost"
(three fields, projection-controlled); low on the ≤ 4-games reading (W2 reverses it).

---

## D1. Saturday build vs T-70 build: what Sunday morning added

Anchors: winners study §6 (active players' projections move 0.26 on average Sat→Sun, MAE 5.361 vs 5.369; all Sunday
value is knowing who is out; W2 error 6.98 → 5.41) and post-mortem §6.2 (Sunday books beat Saturday books both weeks:
W2 98.4 → 106.1 / 105.9; W3 row 1 127.6 → 142.1). Both are consistent with what follows; the split below is new.

**Projection error, Saturday frame vs T-70 frame, over the players our Saturday pool used** (realized 0 for
non-players):

| week | set | players | MAE | bias | MAE, played only | zero-scorers with proj > 3 (projected points carried) |
|---|---|---:|---:|---:|---:|---|
| 1 | Saturday | 349 | 4.76 | −0.68 | 5.12 | 58 (403) |
| 1 | T-70 | 349 | 4.73 | −0.69 | 5.05 | 58 (404) |
| 2 | Saturday | 402 | 4.39 | −1.61 | 4.58 | 57 (458) |
| 2 | T-70 | 402 | **3.52** | −0.69 | 4.50 | 31 (153) |
| 3 | Saturday | 398 | 3.58 | +0.19 | 4.75 | 24 (105) |
| 3 | T-70 | 398 | 3.56 | +0.20 | 4.75 | 22 (95) |

Players whose projection moved ≥ 1.0: 26 / 41 / **4** (of 349 / 402 / 398); ≥ 3.0: 3 / 31 / 0. W2's movers are all
availability zeroings (Flowers 22.6→0, Tua 17.5→0, then twelve backup QBs at 13–16→0); W1's are cheap-slot reshuffles
with no realized signal (Meeks 0.9→5.5 scored 0; Hunter 7.3→3.7 scored 2.1; Mayer 4.6→7.8 scored 9.2; Douglas 3.1→5.9
scored 14.4); W3's largest is Jadarian Price 8.9→10.6 (scored 2.2). Among players who played, the mean absolute move
was 0.38 / 0.26 / 0.11.

**Best available book under each projection set, same selector (top-K by mean, overlap ≤ 7), realized:**

| week | Saturday pool × Saturday proj | Saturday pool × T-70 proj (= news effect) | Sunday 09:10 pool × own proj | T-70 pool (D800) × own proj |
|---|---:|---:|---:|---:|
| 1 | 172.7 (proj 130.8) | 168.3 (−4.4) | 163.8 (D800) | 163.2 |
| 2 | 71.0 (proj 143.4) | **94.0 (+23.0)** | 101.6 (D3200) | 97.3 |
| 3 | 151.4 (proj 130.6) | 148.5 (−2.9) | 134.0 (D3200) | 135.3 |

So: the *news* effect (same rows, Sunday projections) is +23 in the defect week and −3 to −4 noise in the clean weeks;
the *dose* effect (the Sunday pools are 800–3,200 rows against 12,559) is −13 to −15 in W3 and −5 in W1, and +3 to +8
in W2 only because the Sunday pools were *generated* on cleaned projections. The post-mortem's "Sunday row 1 142 vs
128" (W3) is the T-70 D800 pool's top row (my table: 142.1) — one draw from a smaller pool, not information. Projection
error split: the top-mean book's realized minus projected is +42 → +37 (W1), −72 → −42 (W2), +21 → +18 (W3) — Sunday
projections do not change the residual in the clean weeks. Confidence: high (agrees with §6 of the winners study by an
independent route). Sadiq (W3) is the one true Sunday item and it reached the T-70 frame only through the depth chart
(HANDOFF 08:27 CDT 09-28: TE1 already; Isaiah Williams turned O at 10:44 CT, after the 10:29 pull).

---

## D2. What arrives after T-70 (from the hourly DK salary pulls in `nfl_raw.dk_salaries`, the frames, and the late-swap reads)

Information times: DK pulls are hourly at :02–:05 (W1), :45–:49 (W2), :29 (W3); the T-70 frames used the pull of
15:04Z (W1), 15:49Z (W2), 15:29Z (W3) — i.e. **W1 and W3's T-70 projections pre-date the 15:30Z inactives**; the last
pull before lock was 16:02Z / 16:49Z / 16:29Z; **no pull exists after lock**, so late-game (20:05Z / 20:25Z) inactives
are invisible in this table and only the R4 ESPN feed sees them.

| week | status changes after the T-70 frame pull, before lock | of which to OUT/IR | Q cleared (active) | newly-OUT players' share of entered rows | activated players in entered rows |
|---|---:|---:|---:|---:|---|
| 1 | 27 | 25 (Kamara, Ty Johnson, Jalen McMillan, Sean Tucker, 13 backup QBs/TEs at 2.5–4.4k) | 2 | 0.0% | Odunze 2.5% |
| 2 | 1 | 1 | 0 | 0.0% | (Burrow, Olave, McMillan cleared *before* the T-70 pull; 3.1% / 7.2%) |
| 3 | 37 | 29 (Mitchell Q→OUT, Bech Q→OUT, and 27 backups/blocking TEs at 2.5–4.2k) | 8 (Warren, Coker, DJ Moore, Pittman, Spears, Coleman, Lance, Miller) | 0.0% | Warren 2.1%, Coker 4.2%, Moore 0.7%, Coleman 0.7% |

What else moved: totals moved at most 1.0 point Saturday→T-70 in every week (1 / 2 / 3 games of 12–13 moved ≥ 1.0);
wind is a Saturday input (the frame's `wind_mph` is identical in the Saturday and T-70 frames): W2 MIN-CHI 14 mph, W3
five games at 12–17 mph (CAR-CLE, CIN-PIT, LAC-BUF, SEA-WAS, TEN-NYG; two of them were the slate's shootouts); W1's
frame carried no wind. So after T-70 the only new information is (a) the inactives list itself — which the W1/W3 T-70
frames had not yet seen but the vetting/replacement step handled (newly-OUT exposure 0.0% in the entered book every
week; the pool still holds them: 20 of 29 in W3 were "in pool") — and (b) Q players declared active. (b) is the one
exploitable item on the mean track: HANDOFF 09-28 replay: with `T70_ACTIVE_Q=1` Warren 11.6→14.6 (actual 23.6), DJ
Moore 8.3→10.5 (12.7), Coker 10.0→12.6 (3.8); the ten activated Q players in W3 carried market 101.8 / served 84.9 /
actual 102.6 — about 1.7 points per activated player of under-projection, worth about 0.2–0.5 points per entered row at
our 0.7–4.2% exposures, more if the mean track buys them. Late-game news after lock: L11 (frozen rule) measured the
satellite late-swap at +11.1% tickets at p89 and +16% at p95 with paired slate-banks 30–32–10 — NOT SUPPORTED by its
rule; on the mean track it is +1.66 realized per row and +2.83 on the swapped rows, lumpy. The smoke
(`smoke-late-swaps.json`, W3) shows the mechanics (Flowers→Pickens/McBride in 5 rows). Confidence: high on the timeline
(it is the DK pull log); medium on the value of (b) (one week, ten players).

---

## D3. Residual availability loss after the repairs

Players who scored 0 (or had no DK/nflverse record) with projection > 3, weighted by their usage; "lost" = projected
points per row carried by such players (an upper bound on what a perfect availability model recovers, since some of
these played and scored 0).

| week | book | zero-scorers used | rows affected | projected points lost per row | by class |
|---|---|---:|---:|---:|---|
| 1 | entered (80) | 9 | 28% | **2.67** | depth-1 1.38 (Loveland 10.9 at 6% — played, scored 0; Pitts), depth ≥ 2 1.14 (Addison 10.4 at 5% — suspended; Bateman 7.7 at 6% — inactive), backup QB 0.15 (Rattler) |
| 1 | Saturday pool | 61 | 45% | 4.83 | backup QB 2.23 (Rattler 13.5% of rows, Flacco), depth ≥ 2 1.62, depth-1 0.98 |
| 2 | entered (97) | 6 | 13% | **0.84** | depth-1 0.50 (Gesicki 7.6, Jeudy 7.2, Mason Taylor 5.5), depth ≥ 2 0.35 (Bates, Cameron, Sample) |
| 2 | Saturday pool | 61 | 59% | 11.82 | depth-1 7.66 (Flowers 22.6 in 31.8% of rows = 7.2 alone), backup QB 2.78 (Keenum 6.4%, Mills, McCarthy, Lance), depth ≥ 2 1.38 |
| 3 | entered (144) | 5 | 10% | **0.64** | depth ≥ 2 0.64 (Gadsden 8.1 at 5.6%, Palmer 5.1, Dyami Brown 4.9, Wester 4.0, Oliver 3.6) |
| 3 | Saturday pool | 25 | 26% | 1.54 | depth ≥ 2 1.52 (Palmer 7.0%, Gadsden 3.7%, Mitchell 3.2% — Q at build, OUT 10:44 CT), depth-1 0.02; **no backup QB** |

Reading. The repairs (backup-QB gate, Doubtful as absence, Q-primary scale, LIVE_MIN_PROJ) took the pool's availability
load from 4.8 (W1) and 11.8 (W2) to 1.5 projected points per row in W3, and the entered book's from 2.7 to 0.6; no
backup QB and no OUT/D player reached the W3 pool. What remains is one class: **depth ≥ 2 WR/TE at 2.5–3.5k projected
4–8 who are inactive or healthy scratches** (Gadsden, Palmer, Dyami Brown, Wester, Bech, Devontez Walker, Jeudy) — the
punt band again, entered at 0.7–5.6% each. That is 0.6 points per entered row (about 1.5 in the pool) — small against
the 30-point selection gap, and mostly not "Out/Doubtful" but low-depth players with no prop line. The realized
counterpart from B2: depth ≥ 3 duds in 55 of 144 W3 rows, replacement gain 2.9 per holding row. The unmatched question
from the status study (`status_predicts.py`, W1–W2: Q plays 77%, D 0 of 13) stands; Q players who reached the entered
book in W3 (7 players, max 6 of 144 rows) all played. Confidence: high (three weeks, exact usage weights). Unknown: how
many of the W3 residual zeros were pre-lock knowable (Palmer and Gadsden: DK status blank at 16:29Z; a depth-chart or
prop-line rule would catch them, the DK status would not).

---

## Immediate actions (this week, no new model), with the evidence and a confidence

1. **Select the satellite (mean-track) book by projected mean from the lev rows, with the 50% exposure cap that is
   already armed** — B1: +29 / +31 realized per row over the entered expected-max book in the two clean weeks, 64% / 51%
   above the cash line vs 20% / 10%; residual analysis says the expected-max selector systematically picks rows that
   under-realize. Already adopted for Week 4; the point here is the evidence and the caveat: uncapped, the top-mean
   book is one core (Gibbs 96–100%), and on the W2 defect pool it lost by 34. Confidence high on the direction, medium
   on the capped magnitude.
2. **Cap punts at three per row in the mean track and drop the 4-punt lev rows before selection** (a filter on the
   existing pool, no solve) — B3: 4-punt lev rows realize 13–24 below 3-punt lev rows in both clean weeks (cash 3% vs
   42%; 19% vs 45%); the valuation overstates every punt slot by 9–14 points and ranks punts no better than the mean.
   Then run Q4b (plain-mean lev batch) as the lab has it queued. Confidence medium-high.
3. **Keep the QB+2 + bring-back mandate on the mean track; do not add a 5+-games rule** — B5: field rows with our
   shape score +3 to +5 and cash 26–27% vs 18% in all three weeks; given the projection, 4-game rows beat 6–7-game rows
   in W1 and W3. Confidence medium-high.
4. **Punt-band availability rule for the pool**: exclude (or MIN_PROJ-gate) depth ≥ 3 WR and depth ≥ 2 TE priced
   ≤ 3.5k who have no prop line at the T-70 pull — B2/D3: this class is the entire residual availability loss in W3
   (0.6 per entered row, 1.5 in the pool) and 37 of the 74 W3 dud slots outside the punt valuation. It is a universe
   filter, not a model. Confidence medium (the rule's false-positive rate on players like Juwan Johnson / Sadiq must
   be checked on the three frames first — both are depth-1, so they pass).
5. **Sunday sequencing: DK pull after the 10:30 CT inactives and before the T-70 projection, and `T70_ACTIVE_Q=1`** —
   D2: the W1 and W3 T-70 frames were pulled at 10:04 / 10:29 CT, before the inactives; 27 / 37 status changes landed
   in the next pull; the eight W3 Q-activations (Warren 23.6) were under-projected by about 1.7 each. Already in the
   Week-4 handoff; this is the confirmation from the pull log. Confidence high.
6. **Do not spend Sunday re-projecting active players** — D1: MAE and residual unchanged in the clean weeks; 4 of 398
   players moved ≥ 1 point in W3; the Sunday pools' lower dose cost 13–15 points of top-mean book in W3. Change only what
   the news requires (winners study §6, recommendation 5). Confidence high.
7. **A paper read only, not an entry change: stud WR/RB under-projection** — B4: WR 6.5k+ +2 to +5 and RB 7.5k+ +4.4
   this season on n = 8–26 against +0.6 / 0.0 historically; the top-8 projected WRs beat projection all three weeks.
   Log the served-vs-market gap for 7k+ WR/RB weekly; do not hand-edit projections. Confidence low on magnitude.

What remains unknown and would change these numbers: the capped top-mean book's realized mean on these three pools
(the lab's L18 replay is the only read); a re-solved plain-mean lev batch (Q4b); satellite-line ticket rates by
construction (needs the per-contest ladders); whether the 2026 stud under-projection is the one-season-window artefact.
