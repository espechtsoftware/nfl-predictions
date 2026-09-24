# Corpus, selection and sorting: where the next points are

**2026-09-24.** The operator asked for two things: a review of what changed since the external reviews of 09-22,
and research into three levers:

- adding better-scoring lineups to the corpus;
- selecting from the corpus;
- sorting, so the best lineups appear first.

**How this was checked:**

- Every number was recomputed today from the scripts in `reports/lab-handoffs/2026-09-24-corpus-selection-sorting/`
  (README there).
- Every claim about the team's work was checked against HANDOFF, the lab's `LEDGER.md` and the reports they cite.
- The data stays outside the repo. The analysis ran on one core beside the running L03 panel, and nothing touched the
  money path.

The historical analyses use slates that earlier panels already read. They **nominate**; they do not adopt. Each
proposal carries the test that would decide it.

---

## 1. Summary

1. **Corpus: ownership is the lever that holds up; the stack rule is not.**
   - **Where the winners are.** In the real 2026 Millionaire fields, some lineups had at most one predicted
     low-owned player. They reached the top 0.1% at **1.5× (Week 1) and 1.7× (Week 2)** their share of the field.
   - **Where our pool was.** 4% of our Week-2 pool was there, against 40% of the field. The historical pools agree
     (+3.2 points).
   - **L02 was a near miss on noisy labels.** A quarter of the winners' 20%+-owned players were labelled low-owned.
     Its successor should rerun the sleeve on the better lag-feature labels. It should add an actual-ownership arm
     that shows how much the mechanism can do at best.
   - **The stack rule.** Most top-0.1% lineups break the house stack rule (77–90%), but mostly because most entrants
     do. Per lineup, house-legal lineups did better than the field in Week 1 (2.3×) and the same in Week 2 (1.0×).
     The lab's catcher-relaxation arms already failed (PREREG-053). **The relaxed-stack sleeve from my 09-22 review
     (its item 3) stays an optional arm, ranked last.**
2. **Selection: keep dual expected-max.** On 107 historical pools nothing tried raised the book's best lineup.
   - A 3-point penalty per predicted low-owned player raises the book's average (+0.5, t 4.4, 6/6 seasons) at no
     measurable cost to its best. That makes it a lever for cash lines, not the top prize.
   - Hard chalk filters cost about a point of ceiling.
3. **Sorting and layout: the layout matters more than the sort key.**
   - **The "no key" finding.** Two studies found no reliable sort key on two slates. On 107 slates, keys based on
     simulated mean or predicted ownership correlate +0.17 with the realized order on average. They are still
     negative on a fifth of slates. A key that good passes the two-week test only about a quarter of the time.
   - **`top` layout.** Giving every contest the book's top rows adds **4.0–4.4 points to each contest's best lineup
     and 3.5–5.7 to its average** (6/6 seasons). The operator chose unique lineups per contest on 09-18 for a reason
     that still stands; the choice is theirs.
   - **Snake deal.** This keeps unique lineups per contest, but deals the rows round-robin in payout order, sorted
     fewest-low-owned first. It adds **+1.75 to each contest's average** (t 3.2, 6/6 seasons) and +1.1 to its best
     (not significant). The 23-entry contest gives up about 4 points on its best lineup.
   - **Today's blocks, sorted fewest-low-owned first.** This makes things worse: −1.8 on each contest's best.
4. **Review of the last two days.** The work was strong and disciplined, and I accept three corrections to my earlier
   reviews. My concerns:
   - L02 probably understated the sleeve.
   - The unique-lineup layout's cost in points has not been set against its benefit.
   - Lev's build time looks large next to its share of the book.
   - From Week 4 one laptop runs both production and the lab.

---

## 2. What changed since 09-22, and my view

| area | what the team did | view |
|---|---|---|
| chalk-core sleeve | Built in nfl2 (`0f03b782`, default off, refused together with the live A5 sidecars, so paper only; 12/12 tests). PREREG-L02 frozen and read once. **SLEEVE_L2 (≤2 low-owned) a near miss**: better in both seasons (finish share above the book's best 0.0212 → 0.0169; 90% upper bound +0.0010); co-reported book best +3.7, books reaching 194 34 → 44. SLEEVE_L1 mixed. SLEEVE_L2 runs as arm (c) of the Week-3 paper triple, scored Monday by `paper_arm_outcomes.py`. | Fast and disciplined. The sleeve changed most of the book (31–37 of 80 lineups shared with control). Its labels were noisy, so L02 is likely an underestimate (§3.3). |
| max-per-game 4 | L01 read: flip-eligible (pool oracle better in 3/3 seasons; book-level gain small). ALLBOOM_CEIL not flip-eligible. | Agree. The cap keeps 94% of historical winners (09-22 review), so it is low-risk. |
| ownership model | `scripts/ownership_sets.py`, walk-forward, base model 0.75–0.77 (history). Optional lag inputs (aligned `8ce82ef4`, default off) lift history to 0.78–0.79. On Week 2 live they add +0.06–0.07 on Sunday-morning projections and +0.17 on Saturday's; production retracted the single "0.64 → 0.81" headline. | The best input the sleeve can get. Use it in L02's successor (§3.5). |
| market | Bias confirmed: WR rises with the line, to +2.5 at lines of 18+; RB +1.0 to +1.6 by season. Bonus-aware and median-line conversions built on parked branches, default off. L03 replay at 29/72, read tonight. L04 props-blend re-test drafted (nfl2 `f1105f2`). | A good sequence. L03 and L04 decide at lineup level, as they should. |
| substrate census | Found that the lab's 2023–24 replay snapshot prices ~98 depth players per slate from a single market. Listed the exposed lab verdicts: the blend (PREREG-007), the centring (PREREG-011), P_MIX, DUAL_EMAX. | Important. Any re-read needs a new preregistration, as the census says. |
| scoreboard | Heavy-user benchmark and corpus shares added (`170ca425`); paper-arm scoring added today. Week-2 read: on honest projections the book was level with the field; the loss was the fixed defects. | Done as asked. |
| Route Share | Weekly stopping rule declared before any read (false-alarm rate at most 0.094). | Done as asked. |
| availability | Backups behind a Questionable QB scaled ×0.20. Returning-teammate adjustment deployed; its audit found no defect. Returning-RB side built, default off (no Week-3 case). | Reasonable in-season adoptions with verification. |
| cutover | Production moves to the laptop from Week 4. Move document and checklist written. `main` fast-forwarded to `d5705e93`. | The laptop's CPU becomes the bottleneck (§6). |

**Corrections to my own reviews:**

- **`own_shadow`.** Production is right that its `booster_own` column is usable (+0.63). My −0.11 was the naive
  `pred_own` column.
- **House legality.** The "12% vs 43 of 51" conflict is not a conflict. August's anatomy counted 43 of 51 winners
  *illegal* (16% legal), and my registry pass found 6 of 50 legal (12%). Both say the same thing.
- **Ownership Spearman.** My 0.83–0.87 for the 2026 live frames is not comparable with production's 0.62–0.68. It
  covers every DK-listed player, fringe zeros included, and uses Sunday's last projections. The decision-relevant
  number is label quality (§3.3).

---

## 3. Corpus: adding the lineups winners are made of

Labels throughout come only from pre-lock *predicted* ownership (a walk-forward model on our own features):

- **LOW:** a skill player outside the top 10.1% of the slate's skill players, as in production's sets file;
- **CHALK:** one of the top 15 players.

The sleeve region is ≥1 CHALK and salary ≥ $49,500, plus ≤1 LOW (L1) or ≤2 LOW (L2).

### 3.1 Chalk-core lineups beat the field per lineup, and our pool barely has them

Share of the real 2026 Millionaire lineups inside each region:

| | L1, W1 / W2 | L2, W1 / W2 |
|---|---:|---:|
| field | 58.5% / 40.1% | 81.3% / 71.6% |
| top 1% | 80.0% / 65.9% | 93.2% / 87.4% |
| top 0.1% | 86.4% / 68.0% | 94.8% / 89.0% |
| top 100 | 91.0% / 69.0% | 96.0% / 87.0% |
| **lift at the top 0.1%** (its share ÷ the field's) | **1.48× / 1.70×** | 1.17× / 1.24× |
| our Week-2 pool (12,555) | — / **4.0%** | — / **18.2%** |

The L1 region beats the field per lineup in both weeks, and our pool held a tenth of the field's share.

### 3.2 The stack rule: what winners hold is not the same as what wins per lineup

Here "lift" means a region's share of the top 0.1% divided by its share of the field. All rows are under the cap of
4 players per game.

| rule set | W1: top 0.1% / field / lift | W2: top 0.1% / field / lift |
|---|---|---|
| house rules (QB + 2 pass catchers + bring-back, ≥ $49k) | 23.1% / 9.9% / **2.3×** | 10.5% / 10.9% / **1.0×** |
| house rules inside L2 (the current sleeve) | 22.6% / 8.4% / 2.7× | 9.3% / 8.4% / 1.1× |
| QB + ≥1 pass catcher, bring-back optional, inside L2 | 73.2% / 60.1% / 1.2× | 81.4% / 56.1% / 1.5× |
| QB + ≥1 pass catcher inside L1 | 66.9% / 44.0% / 1.5× | 62.8% / 31.8% / 2.0× |

Reading:

- **What winners hold.** A pool built only under the house rules cannot contain 77% (W1) to 90% (W2) of the top-0.1%
  lineups. Read alone, that argues for relaxing the rule.
- **What wins per lineup.** House-legal lineups reached the top at 2.3× their field share in the Week-1 shootout and
  1.0× in Week 2. Relaxed lineups did so at 1.2× and 1.5×. Neither shape wins per lineup in both weeks: it is the
  "shootout bet that nets out" the lab found for the bring-back. Most winners are relaxed because most entrants are.
- **History.** The lab has tested relaxation at equal solves several times:
  - single-partner and no-stack sleeves (016): negative or null;
  - legality-only construction (PREREG-015): the house rules were worth about +3.6;
  - catcher relaxations on tail worlds (PREREG-053): T_FREE_TAIL's interval lay entirely below zero. Only dropping
    the bring-back converted, at D400, and PREREG-055 found that gain absorbed at D800.
- **So what the winners hold does not justify relaxing the rule.** The one new element would be combining relaxation
  with the chalk-core constraint, as my 09-22 review proposed (its item 3). I keep that as an optional arm only
  (§3.5).

The registry agrees on shape: of 50 historical winners with a full team match, 8% are house-legal under the cap and
28% are relaxed inside L2. It has no field to compute a lift against, and its labels are noisy (§3.3).

### 3.3 Why L02 probably understates the sleeve

L02's labels came from the base ownership model run on replay projections (walk-forward Spearman 0.75–0.77). Replay
projections do not carry the crowd's Sunday news.

I ran a model of the same kind on the same replay projections, over historical winners' players. Of those actually
**20%+ owned, 26% were labelled low-owned**; of those 10–20% owned, 32%. A sleeve steered by those labels spends part
of its budget in the wrong place. So L02's near miss is more likely an underestimate than an overestimate. That is a
reason to rerun it with better labels, not to adopt it.

Live labels are better, but they depend on timing:

- **Sunday.** On the last pre-lock projections, my labels were 99% precise (98.8–99.5%) with 96% recall.
- **Friday/Saturday,** when production builds the sets file. On Week 2's Saturday frame the base model's Spearman
  was 0.64, against 0.78 on Sunday's. The lag inputs recover +0.17 on the Saturday frame.

PREREG-L02 reopens only on a new mechanism, for example a better chalk predictor. The L02 report itself names the
aligned lag model as the candidate.

### 3.4 What the historical pools say about which candidates win

Setup:

- 107 replay pools: 25,782 candidates, about 240 per slate, 2019 and 2021–25.
- Each candidate's realized score is compared with its slate's mean.
- "Top-5 lift" is how often a group lands among a slate's five best realized lineups, relative to its share of the
  pool.

| group | share of pool | realized vs slate mean | top-5 lift | taken into the expected-max book |
|---|---:|---:|---:|---:|
| boom (one world's optimum) | 17% | −2.9 | **2.07** | 98% |
| lev (projection optimum with overlap cuts) | 66% | +0.4 | **0.57** | 11% |
| candidates with 0–2 predicted low-owned players | 18% | **+3.2** | 1.27 | — |

Notes:

- **Chalk count.** Holding simulated mean and q99, low-owned count and salary fixed, each predicted-chalk player
  adds +0.96 realized points (se 0.39).
- **The ceiling evidence is §3.1's, not these pools'.** Top-5 lift is not monotonic in the low-owned count: 0–2 LOW
  gives 1.27, 3–5 gives 0.90–0.93 and 6+ gives 1.13. The historical support for chalk-core is on the average.
- **Three generators today's pool does not have.** The replay pools also held `qbvar`, `game` and `dark`
  candidates. Each reached a slate's top 5 at 1.5–1.7× its pool share; lev is the only generator below 1. Today's
  pool is lev and boom only. Whether any of the three belongs back is a question for the lab; I have not checked why
  they were dropped.
- **Lev live.** Lev is 20% of the D12800 solves but 2–8% of books (1.9 of 80 in L01's control, 8 of 97 in Week 2).
  Per production's cost note it is most of the ~10-hour build, against about 17 minutes for boom-only.

### 3.5 Proposals, in order

1. **PREREG-L05: L02's successor on better labels.**
   - **Arms:**
     - CTRL;
     - SLEEVE_L2 exactly as frozen in L02 (share 0.25, ≤2 LOW, ≥1 of the top 15, salary ≥ $49,500, house rules),
       with sets from the aligned lag model (`--lag-features`, `8ce82ef4`);
     - a diagnostic arm: the same sleeve on actual-ownership labels.
   - **Why the diagnostic arm.** It cannot be adopted, since ownership is known only after lock, but it separates
     the two ways L05 can fail. If even the oracle arm fails, the sleeve is dead whatever the predictor. If it
     passes, the predictor is the bottleneck.
   - **Optional third arm:** the relaxed stack inside the same sleeve. Include it only if the lab judges the
     chalk-core constraint a new mechanism relative to PREREG-053's failed catcher relaxations. I rank it last.
   - **Share.** Keep 0.25: the L02 sleeves already replaced 43–49 of 80 book lineups.
   - **Design.** Same primary and freeze discipline as L02.
2. **Decide whether lev earns its build time.**
   - L01's all-boom arm tied the control at equal solves: 90 vs 92 books reaching 194. It was not flip-eligible, but
     that is not the same as non-inferior.
   - Lev supplies 2–8% of books and most of the ~10-hour build; on one laptop from Week 4 those hours matter.
   - A non-inferiority reading of L01's all-boom arm, or a small panel, would show whether dropping lev costs
     anything. This is an operational question more than a scoring one.
3. **Not proposed:** adding ownership-sampled field lineups to the corpus, an idea from my working notes.
   - The sleeve already builds chalk-core lineups that are optimal in some simulated world, which is what the
     selector rewards.
   - PREREG-098's finish-probability selection on the same sampler was decisively negative.

---

## 4. Selection: what the selector can and cannot do

**Setup.** On the same 107 pools, each selector builds an 80-lineup book, scored on realized points. Dual
expected-max is recomputed greedily on each pool's archived world matrix.

| selector | book best | book mean | best vs expected-max | mean vs expected-max |
|---|---:|---:|---:|---:|
| expected-max (greedy, live form) | 176.74 | 116.62 | — | — |
| the panel's own coverage-194 book | 176.66 | 117.06 | −0.09 (t −0.3) | +0.43 (t 2.8) |
| top 80 by simulated mean | 170.53 | 120.13 | **−6.21 (t −5.0)** | +3.51 (t 4.3) |
| **expected-max, −3 points per predicted-LOW player** | 176.47 | 117.15 | −0.27 (t −1.0) | **+0.52 (t 4.4, 6/6 seasons)** |
| expected-max restricted to ≤2 LOW (then fill) | 175.54 | 117.90 | −1.21 (t −2.1) | +1.27 (t 3.4) |
| expected-max restricted to chalk-core (then fill) | 175.72 | 118.12 | −1.03 (t −2.6) | +1.50 (t 3.8) |

Reading:

- **Expected-max is still the right engine.** Mean-only selection gives up six points of ceiling.
- **The low-owned penalty raises the average without a measurable ceiling cost.** That helps cash lines and
  multi-entry contests, not the top prize, so it is low priority. (Its mirror image, the chalk fade in lev solves,
  did not replicate across two slates.)
- **Filters buy mean at the cost of ceiling.** The median pool had 17 chalk-core candidates out of 240, so a filter
  mostly throws away the tail. Selection cannot supply what generation does not build, which is why §3 comes first.

---

## 5. Sorting and layout

### 5.1 Today's order, and what two slates can show

**Today's order.** The money path enters rows in greedy expected-max order:

1. `exposure_cap_book.py` re-selects with caps.
2. Vetting moves flagged rows to the back.
3. With `PROMOTE_FIRST_ENTRY=1`, the MEAN promotion puts the highest-mean clean lineup among the first 30 in row 1.

The greedy's first pick is already the highest-mean lineup, so greedy order is the baseline below.

**The two-slate studies.** Production measured simulator keys at +0.28 (W1) and −0.16 (W2) within-book correlation.
The laptop's 09-22 study found no key that met its rule: same sign both weeks, p < 0.10 in both.

Across 107 books, the within-book Spearman correlation between a key and the realized score averages:

- simulated mean: **+0.17** (sd 0.19 across slates; negative on 22% of slates);
- predicted ownership sum, low first: **+0.18** (negative on 21%);
- the greedy order itself: +0.01 (negative on 42%).

A key as good as the 107-slate average shows opposite signs on two slates about a third of the time. It passes the
two-week rule only about a quarter of the time. So the two-slate result is what a weak real key looks like; it does
not show the keys are useless.

### 5.2 Within-book order on 107 books

Each pool's 80-lineup expected-max book is re-ordered. Each order is scored on the realized mean of its first rows.

| order | row 1 | first 10 | first 30 | first 10 vs greedy | first 30 vs greedy |
|---|---:|---:|---:|---:|---:|
| greedy (today) | 123.97 | 119.23 | 117.37 | — | — |
| simulated mean | 123.97 | 121.62 | 120.73 | +2.39 (t 2.3) | +3.36 (t 5.0) |
| **fewest LOW, then greedy** | 123.60 | 122.24 | 120.04 | **+3.01 (t 3.1)** | **+2.67 (t 4.7)** |
| fewest LOW, then simulated mean | 125.17 | 123.31 | 120.76 | +4.08 (t 4.1) | +3.39 (t 5.3) |
| simulated q99 / P(≥194) | 122.26 / 124.01 | 120.24 / 120.13 | 119.58 / 119.45 | +1.0 / +0.9 (n.s.) | +2.2 / +2.1 |

- **Seasons.** The three "fewest LOW" and "simulated mean" orders gain in all six seasons at both depths.
- **Replication.** On the 72 replay books (2022–25), "fewest LOW, then the book's own order" gives +3.12 (t 2.7) on
  the first 10 and +1.83 (t 2.3) on the first 20.
- **Row 1 barely moves.** "Fewest LOW, then simulated mean" puts a 125.2 lineup there against 124.0: +1.2, t 0.4.
  For a single-entry contest, the existing MEAN promotion is as good as anything tested here.

### 5.3 "Best first" has two meanings

The greedy order front-loads *different* scenarios, so its first rows hold the highest **best** lineup, even though
their average is lower.

| order | best of first 10 | best of first 20 | vs greedy (10 / 20) |
|---|---:|---:|---|
| greedy (today) | 159.15 | 167.00 | — |
| fewest LOW, then greedy | 158.71 | 165.10 | −0.43 / −1.90 (both n.s.) |
| fewest LOW, then simulated mean | 155.23 | 164.42 | −3.92 (t −2.0) / −2.59 |
| simulated mean | 153.22 | 163.19 | −5.93 (t −3.2) / −3.82 (t −2.5) |

**"Fewest LOW, then greedy" is the right default order.** It raises the average of the first rows and leaves the
best of them statistically unchanged. Sorting by projection on the replay books costs −12.9 (t −5.8) on the best of
the first 10.

### 5.4 The layout decides more than the key

**Setup.** Week 2's twelve contests (sizes 1, 23, 1, 5, 1, 2, 10, 10, 10, 16, 16, 2, in payout order; 97 entries) are
replayed on 97-lineup expected-max books from the 107 historical pools. Each contest is weighted equally. Three
layouts are compared:

- **sequential (today, since the operator's 09-18 decision):** each contest takes its own consecutive block;
- **snake:** still one lineup per contest, but rows are dealt one per contest per round in payout order, reversing
  each round, so every contest gets one of the book's top 12 rows;
- **top:** every contest takes rows 1..n.

| layout / order | each contest's best lineup | vs today | each contest's average | vs today |
|---|---:|---|---:|---|
| sequential / greedy (today) | 142.67 | — | 117.10 | — |
| sequential / fewest LOW, then greedy | 140.87 | −1.80 (t −3.3, 0/6) | 116.57 | −0.53 (t −1.2) |
| snake / greedy | 142.71 | +0.04 (t 0.1) | 117.21 | +0.12 (t 0.3) |
| **snake / fewest LOW, then greedy** | 143.74 | +1.07 (t 1.7, 4/6) | 118.84 | **+1.75 (t 3.2, 6/6)** |
| top / greedy | 147.02 | **+4.35 (t 3.7, 6/6)** | 120.55 | +3.45 (t 3.6, 6/6) |
| **top / fewest LOW, then greedy** | 146.68 | **+4.02 (t 2.9, 6/6)** | 122.84 | **+5.74 (t 4.6, 6/6)** |

Reading:

- **Unique lineups fix the average over all entries.** Under any unique-lineup layout, the average over all 97
  entries cannot change: the same 97 lineups are entered once each. Only which contest gets which lineup changes.
  `top` changes the lineups themselves: the book shrinks to the largest contest (23 in Week 2), and every contest
  gets the best rows.
- **Sorting today's blocks backfires.** Sorting fewest-low-owned first concentrates the good rows in the first
  contests, and the later blocks get worse.
- **Snake with fewest LOW keeps the operator's rule** (no lineup in two contests) and gives every contest an early
  row. The small contests gain: for example the pylon's single entry goes from 115.0 to 120.4, and the two-entry FFWC
  qualifier from 128.5 to 133.2. The 23-entry flea's best falls from 168.0 to 163.8.
- **`top` gains most.** Its cost is the operator's 09-18 concern: the same lineups in several contests, so one bad
  lineup or one injury hits them all. Since 09-18, several steps address part of that risk:
  - Doubtful players are capped at zero rows;
  - per-contest exposure caps sit inside the selector;
  - vetting replaces confirmed-out players.

  The choice remains the operator's.
- **Not modelled:**
  - **Ticket values.** The 09-18 analysis showed that for satellites, distinct blocks raise the chance of at least
    one seat (35% → 58% at a 190 cutoff) at about a 15% cost in expected seats.
  - **Prize sizes.** Weighting contests equally ignores them.

---

## 6. Suggested next steps

| when | what | who | cost |
|---|---|---|---|
| Week 3 (the entered book does not change) | Monday: add a layout line to the paper-arm scoring, showing what each contest would have held under `top` and under the snake deal, with the fewest-LOW order. One week illustrates; §5.4 is the evidence. | laptop | minutes |
| operator decision, from Week 4 | Choose the layout: (a) `top` with "fewest LOW, then greedy"; (b) unique lineups dealt snake-fashion with "fewest LOW, then greedy"; (c) today's blocks in greedy order. (a) is an existing `week_env.sh` switch. (b) needs one new position-to-contest map shared by `exposure_cap_book.py` and the ENTER writer (`sunday_after_build.sh`, `relayout_enter.sh`), plus tests. The fewest-LOW order needs the sets file at build time. Either change needs the money-path validation trail. | operator; production builds | small |
| next lab slot | **PREREG-L05** (§3.5 item 1). Run it on the lab's Cloud Run lanes if at all possible: from Week 4 the laptop is also the production host, and a 14–20-hour local panel competes with the Saturday build. | laptop (lab role) | one panel |
| after L05 | The lev decision (§3.5 item 2). The low-owned penalty in expected-max at live dose (§4), low priority. | lab, operator | one read or panel each |

---

## 7. Limits

- **The 107-pool test bed is an older regime.** It is August's: ~240-candidate pools, K=1, 80-lineup books. Today's
  D12800 pools feed 97–198-entry books. Live books drawn from 12,555 candidates may be more homogeneous than these,
  which would weaken any sort key. Directions should transfer; magnitudes may not.
- **The archived world matrices are generation worlds.** Expected-max read on them is slightly optimistic for boom
  lineups, by about 0.007 points of expected max per boom lineup.
- **The ownership predictions are leave-one-season-out,** for 2022–25; 2019 and 2021 are predicted from later
  seasons. Ownership is not the outcome, so this does not leak points, but it is not strictly walk-forward.
- **The 2026 shares and lifts (§3.1–3.2) come from two slates.** They hold for ownership in both weeks and flip for
  the stack rule, which is the basis for §3's ranking. They use Sunday's last pre-lock projections; the sleeve's sets
  file is built earlier, where labels are noisier.
- **The layout replay weights contests equally** and models neither tickets nor prize sizes.
- **These are already-examined slates.** Everything here is a nomination. L05 and any live change need their own
  frozen tests.

## 8. Reproduction

See `reports/lab-handoffs/2026-09-24-corpus-selection-sorting/README.md`. `layout.py` there produces §5.4, including
the snake deal. It builds on the external-review scripts under `reports/lab-handoffs/2026-09-22-external-review/`
(now on `origin/main` and the integration branch).
