# Week 3: a review of the post-mortem, and the changes that would matter

**2026-09-28, for the operator and both agents.** The operator asked for a thorough review of what happened on Sunday, of
the post-mortem, and for a document of suggestions for major changes. I read the post-mortem, the laptop's critique, the
weekend's HANDOFF, the L04/L05/L09/L10 reads and the two-track plan, and then tested the parts I disagreed with on the
warehouse, the archived Week-3 pool (private bucket) and the 107-slate historical panel. Scripts are in
`reports/lab-handoffs/2026-09-28-week3-review/` (README there). All data stays outside the repo; no user names or
dollar figures appear here.

**One thing first, on my own account.** The `fewest-LOW` entry order came from my 09-24 review. On Sunday it moved two
average rows into the shared head and pushed the 178.9-point row out; the book's own order would have paid five tickets
instead of one. My replay had measured +2.6 points on the head, with week-to-week noise far larger than that, and it was
adopted within a day without a paper week. Section 8 says what I take from it.

---

## 0. The findings, in order of importance

1. **Satellites do not pay the average lineup. They pay the top 0.2–9%.** The post-mortem's central claim, "about 80% of
   the money was in contests where an average lineup of 150+ pays", is wrong about the lines. From the 45 settled
   contests (§2): the $2 11-entry satellites paid at 169 (the 91st percentile of their field), the 594-entry supersats
   at 174 (96th), the FFWC qualifier at 177 (95th), the 190- and 2,378-entry supersats at 190–193 (99th), the wildcats at
   190 (99th), the $4,444 satellites at 197–206 (99.8th). About half the satellite stake sat behind 99th-percentile lines.
   The two-track plan sends all of those to the "mean" track, and L09/L10 measured tickets at the 89th and 95th
   percentiles only. The plan is aimed at the wrong lines for half the money.
2. **At the rake we pay, a field-average book loses 9–16% per week, and our best selector is field-average.** Every
   contest type needs a per-entry ticket rate of 1.10–1.19× the field's to break even (§2). The historical MEAN book
   (L09/L10, 72 slate-banks) clears the satellite lines at 0.9× the field's rate; EMAX at 0.8×. Week 3's mean-track
   rehearsal (20 paid entries of 204, in-sample) is about 1.0×. So the system, at its best measured setting, is a
   field-average entrant paying full rake. Sunday was the expectation plus the EMAX selector plus bad variance.
3. **The winners' lineups are a learnable class, and the class is not what our simulator picks.** A logistic model of
   "finished in the top 1%" fitted on two weeks' Millionaire fields (1.17M entries; features: our projection percentile,
   stack, bring-back, salaries by position, TE at FLEX, the QB's game total; no ownership) finds top-1% lineups at
   **1.9× the base rate in Week 1 and 16.7× in Week 3** when scored on the week it was not fitted on. Our projection alone
   gives 1.0× and 0.4×. Applied to **our own Week-3 pool** (fitted on Weeks 1–2), its 144 rows realized **159.3** against
   the mean track's 151.4 and EMAX's 120.5, with 8.3% of rows at 190+ (mean track 4.9%, EMAX 0%), and its top two rows,
   the Millionaire seats, scored 166 and 176 where the simulator's tail sleeve scored 128/110/137 (§4).
4. **The Sunday information gap is a model gap, not just a timing gap.** The model does not move a backup when his
   starter is ruled out (Sadiq stayed at 7.5 from Saturday through 11:03, scored 26.5, and was in 21 of the top 25).
   Historically, same-position backups of an out starter beat our projection by +1.0 (RB +1.6, TE +1.6; positive in
   all five seasons), and the crowd owns them at 1.3–2.3× what our ownership model expects (§5.1). A T-70 rule fixes
   part of this; a Sunday build alone does not.
5. **The Questionable haircut cost real points on Sunday.** Ten Questionable players had a market price and a score:
   the market projected 101.8 points for them, we served 84.9, they scored 102.6. Warren (23.6, 13% owned), Bowers
   (30.6, 0.7% owned), Flowers (15.4, 0.6%), Evans (12.4, 1.1%), Moore (12.7, 1.9%). The haircut stays on a player
   after he is declared active at 10:30, and the flag rule then keeps him out of the head (§5.2).
6. **The pool is built for the wrong objective, and it costs 10 hours.** A plain-mean optimizer solves 144 diverse,
   house-legal lineups on the Week-3 frame in 3 minutes with a projected mean of 133.3; the best 144 of the 12,559-row
   pool that took 10 hours reach 130.6, with more punts (§6). The lev generator's objective values sub-$4k players at
   their 90th percentile, so its optimum has a true mean 6.5 points below the frame's mean-optimum. On 106 historical
   slates the plain-mean optimizer's 40-row book realized +8.0 points per lineup over the pool's best 40 by mean,
   better in all six seasons (§6).
7. **Several things in the plan are not supported by the evidence, and one was adopted on a hindsight number.** The
   0.1 ownership tilt used realized ownership (caught by the laptop, reverted); the market floor is nil at the player
   level historically (MAE 5.826 → 5.833); MAXGAME5 failed L10; the simulator's P(≥line) selection is worse than the
   mean at every real line on the Week-3 pool; the corrected-hsim bank's player shifts carried no information on Sunday
   (correlation with the residual −0.04; ranking by it gave 122 against 151) (§7).

**The changes I recommend (§9):** measure and select at each contest's real line; replace the selector for the
99th-percentile contests and the Millionaire with a field-fitted class model, run as a paper track for three weeks
before any entry; fix the T-70 information (vacated volume, haircut off on activation, late-inactive replacement);
build the satellite pool with a plain-mean optimizer with exposure targets; choose contests from the economics table;
and cut stake until a per-contest ticket rate above break-even is measured on paper. Sections 9–10 give the order,
the tests and the risks.

---

## 1. What happened, and what the post-mortem got right

The facts are the post-mortem's and I verified the ones I could: 45 contests, 204 entries, one ticket; the Millionaire
seat at the exact median; the entered book's mean 120.2 and best 178.9 (my reconstruction from the archived pool and
the official points: 120.2 / 178.9); the pool's best 207 with nine 200+ rows, all Geno + Sadiq; the mean-track
counterfactual 151.4 / 202.4.

**Right, and well done:**
- EMAX selects for the simulated tail and gives up average score; on Sunday it did worse than random inside its own pool.
  The two-track decision follows from that, and L09/L10 support MEAN over EMAX for tickets (+13% and +21%, two banks each).
- The Sunday builds beat the Saturday book both weeks; the D12800 dose bought nothing selection could keep.
- The punt valuation and the selector, not a chalk fade, made the book contrarian in the bad direction.
- The winners' anatomy (cheap QB stack, cheap TE, stud RB/WR, four per game, chalkier than the field).
- The concentration on two DSTs; the swap rule that could not move a TE to FLEX.
- The fail-loud build audit, and the vendor-capture order.
- The laptop's critique and its L09/L10 reads: the "wrong yardstick" point is right and, as §2 shows, understated.

**Wrong or incomplete:** the ticket lines (§2); the tilt (§7); the haircut (§5.2); the hsim bank (§7); the order (§8);
and the plan's main lever for the Millionaire, a simulator tail sleeve that picks 110–137-point rows (§4).

---

## 2. The economics: what each contest pays, what it costs, and who is in it

From the 45 contests' public ladders and settled standings. "Line" is the score at the last paid rank; "base P" is
tickets ÷ entries; "break-even P" is fee ÷ ticket value; "edge needed" is break-even ÷ base, the multiple of the
field's ticket rate an entry must reach to break even.

| contest | fee | entries | tickets | rake | base P | break-even P | edge needed | line | field p50 | line percentile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $2 satellite ×19 | $2 | 11 | 1 | 9.1% | 9.1% | 10.0% | **1.10×** | 169.4 | 133.5 | 91 |
| supersat 2× ×12 | $0.25 | 190 | 2 | 15.8% | 1.05% | 1.25% | **1.19×** | 190.5 | 132.5 | 99 |
| supersat 25× ×3 | $1 | 594 | 25 | 15.8% | 4.2% | 5.0% | 1.19× | 173.8 | 131.7 | 96 |
| supersat 25× ×3 | $0.25 | 2,378 | 25 | 15.9% | 1.05% | 1.25% | 1.19× | 193.0 | 129.4 | 99 |
| wildcat ×2 | $5 | 79 | 1 | 15.7% | 1.27% | 1.50% | 1.19× | 189.5 | 134.2 | 98.7 |
| $4,444 satellite ×3 | $13 | 402 | 1 | 15.0% | 0.25% | 0.29% | 1.18× | 197–206 | 138 | 99.8 |
| $125 FFWC satellite | $1 | 148 | 1 | 15.5% | 0.68% | 0.80% | 1.18× | 214.9 | 131.6 | 99.3 |
| FFWC qualifier | $18 | 5,000 | 260 places | 15% | 5.2% | — | — | 176.6 | 134.6 | 95 |
| Millionaire | $20 | 161,764 | 37,425 cash | 15% | 23% cash | — | — | 146.4 (min-cash) | 127 | 77 |

**Who is in the fields:**
- The **$2 satellites** are a closed circle. Three users entered all 19 and thirteen entered five or more. Two users,
  one in all 19 and one in 16, averaged **160 points per lineup** and won 10 of the 19 between them; another entered 11
  and averaged 152. Our entered rows averaged 121; the mean-track counterfactual 151, which would have won about 6.
- The **FFWC qualifier**: 73% of entries came from users with 20+ entries (average 136), who took 74% of the paid places;
  the average paid user had 92 entries. It is a professionals' contest.
- The **2,378-entry supersats**: 60% of entries from 20+-entry users, who took 51% of the tickets.
- The **Millionaire**: 34% of entries from 20+-entry users (average 132.7 against 125.1 for single entries), 43% of the
  paid places. 4.6% of entries share their exact lineup with another entry; 2% of the top 100 do.

**What our books achieve against those rates.** The only out-of-sample numbers are L09/L10's, on 72 slate-banks with
144-row books against the sampled field:

| book | tickets at the field's 89th percentile | at the 95th | multiple of the field's rate |
|---|---:|---:|---:|
| EMAX (entered on Sunday) | 8.4–8.6% of rows | 4.0–4.2% | **0.8×** |
| MEAN (the Week-4 plan) | 9.7–10.1% | 4.5–4.9% | **0.9×** |
| field base rate | 11% | 5% | 1.0× |

At the 99th-percentile lines, where about half the satellite stake sits, no panel has measured anything.

**The arithmetic.** ROI at the field's own rate is −rake: −9% in the $2 satellites, −16% everywhere else. At 0.9× the
field's rate it is −18% and −25%. Week 3's mean-track rehearsal (20 paid entries of 204, in-sample, with the exact
ladders) is about 1.0×, and the week it was designed from. The honest statement is: **with the current projection and
the best selector we have measured, the system is a field-average entrant paying full rake**, and the Week-4 plan takes
it from 0.8× to about 0.9–1.0×. Nothing currently adopted or planned gets it to 1.2×.

---

## 3. Where a real edge can come from

A per-entry ticket rate of 1.2× the field's needs one of: information the field does not have when it locks, a
projection that beats the market, lineups that reach the top of the field more often than the field's own, or softer
fields. The evidence for each:

| source | evidence | status |
|---|---|---|
| **Lineups of the winning class** (the shape the field's top finishers share) | §4: walk-forward lift 1.9× and 16.7× at the top 1%; on our pool +8 points over the mean track and the pool's best row found | new; the strongest lead in this document |
| **Information at T-70** (vacated volume, activation, late inactives) | §5: +1.0 historically for backups of an out starter; Q-active players scored the market's 102 against our 85 | partly planned (Sunday build); the model rules are not |
| **Late swap** | the lab closed it three times for the tail (023 −1.23, 024 −0.42, Addendum 67 null); L11 tests the satellite objective today | pending |
| **A projection that beats the market** | none: served MAE 5.93 vs the market's 5.79 on Sunday; L04 says the 0.45 blend beats model-only and 0.70; vendor data no signal; Kalshi none | closed for now |
| **Pre-lock ownership from the crowd** | L05 cell C: oracle labels help, ours do not; the FP projections page is captured from Week 4 (O1) | prospective |
| **Softer fields** | §2: the $2 satellites and the FFWC are the hardest fields per line; the 594-entry supersats have no heavy users | operator's call |

---

## 4. The lineup class that wins, learned from the field

**What I did.** For every entry in the three 2026 Millionaires (1,165,402 entries; the laptop's `milly_shape_lift.py`
features), a logistic regression of "finished in the top 1%" (and separately "top 100") on: our pre-lock projected sum
as a within-week percentile and its square; QB-stack size; bring-back count; most players from one game; QB, TE and
total-RB salary; salary left; TE or RB at FLEX; the QB's game total. Two versions: **shape only** (no ownership; usable
before lock) and shape + the field's ownership sum (post-lock; illustration only). Fit on two weeks, score the third.
Week 2 is not used as a test week: our projection had the backup-QB defect that week, and a model that leans on our
projection collapses with it (lift 0.0–0.2; the fail-loud audit is the guard against a repeat).

**Walk-forward lift** (the model's top X% of entries' rate of finishing top-1% / top-100, over the field's base rate):

| target | model | test week | top 1% of entries | top 5% | top 10% |
|---|---|---:|---:|---:|---:|
| top 1% | shape only | 1 | **1.93** | 2.19 | 2.23 |
| | | 3 | **16.7** | 8.7 | 5.3 |
| | our projection only | 1 | 0.99 | 1.64 | 1.81 |
| | | 3 | 0.43 | 1.16 | 1.47 |
| top 100 | shape only | 1 | 0.0 | 1.2 | 1.5 |
| | | 3 | 19.0 | 8.6 | 6.3 |

Standardized coefficients (fitted on all three weeks, top-1%): projection percentile +1.11 with −1.05 on its square
(the class peaks below the extreme, the optimizer's curse the laptop found); total RB salary +0.51; stack +0.41; QB game
total +0.34; bring-back +0.28; QB salary −0.44; RB at FLEX −0.38; TE salary −0.22. That is the post-mortem's winners'
anatomy as a scoring rule, and the walk-forward rows above show it transfers from week to week.

**Applied to our own Week-3 pool** (12,559 rows; model fitted on the Week-1 and Week-2 fields; realized official
points; K-row books with the overlap cap ≤ 7, as the mean track uses):

| book from the pool | realized mean | best | rows ≥169 | ≥174 | ≥177 | ≥190 | ≥193 | ≥206 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EMAX (entered), 144 | 120.2 | 178.9 | 4.2% | 1.4% | 0.7% | 0 | 0 | 0 |
| mean track (projected sum), 144 | 151.4 | 202.4 | 25.0% | 19.4% | 16.7% | 4.9% | 1.4% | 0 |
| **class model, target top-1%, 144** | **159.3** | **207.1** | **34.0%** | 27.1% | 23.6% | **8.3%** | 5.6% | 0.7% |
| class model, target top-100, 40 | 151.6 | 202.4 | 35.0% | 35.0% | 35.0% | **22.5%** | 17.5% | 0 |
| mean track, 40 | 153.2 | 188.9 | 22.5% | 12.5% | 12.5% | 0 | 0 | 0 |

The pool held 35 rows at 190+ out of 12,559. The top-100 model's 40 rows held nine of them. The simulator's P(≥210)
sleeve, the plan's Millionaire selector, picked rows that scored 128, 110 and 137.

**How to read this.** Two honest test weeks at the field level (1.9× and 16.7×), one week of pool application, and Week 3
was the week that rewarded this shape most (the projection-percentile lift at 80–95th was 1.8–2.0 in Weeks 1 and 3). The
result says the class exists and our pool contains it; it does not say what next week's lift is. What it does establish:
- **the simulator's tail probability is not how to pick Millionaire seats**: it selects on simulated worlds that do not
  contain the class (post-mortem §12: the winners' shape "is the behaviour of a simulation-driven builder with exposure
  targets and no fade, not of a coverage selector"); a model fitted on the real field's outcomes is the direct route;
- the class is **pre-lock computable** (no ownership needed), cheap (a refit each Monday on the growing field data takes
  seconds), and can run as a paper track beside the mean track from Week 4 at zero risk.

**Honest odds for the Millionaire.** Top-100 is 0.06% of the field. With a lift of 6–19× on the model's top rows (Week 3)
and 0–1.5× (Week 1, where nothing reached the top 100), two seats give perhaps 0.5–2% a week at best. "Not possible is
not an option" is a directive; the numbers say it is a lottery whose odds this class model roughly doubles in an
ordinary week and multiplies several times over in a week like this one. More seats multiply that; nothing else we have
does.

**Where this is like, and unlike, what failed before.** The lab's learned selectors (PREREG-096's reranker, the KG
reranker) learned from our own pool's simulated outcomes and reverted on real pools. This learns from the real field's
realized outcomes, refits weekly, and never touches the simulator. The lab's PREREG-098 finish-objective used the
sampled field and failed decisively; this uses the real one.

---

## 5. The information gap at T-70

### 5.1 Vacated volume: the model does not move the backup

On the historical replay panel (2019, 2021–24, where depth charts exist), same-position teammates on a team whose
depth-1 player is Out or Doubtful on the final report:

| depth | starter out | n | our projection | actual | actual − projection | field ownership vs our ownership model (median ratio) |
|---|---|---:|---:|---:|---:|---:|
| 2 | no | 6,425 | 3.98 | 3.69 | −0.29 (se 0.06) | 0.99 |
| 2 | **yes** | 770 | 4.82 | 5.83 | **+1.01 (se 0.24)** | **1.33** |
| 2, RB | yes | 126 | 7.88 | 9.52 | **+1.64 (se 0.70)** | **2.14** |
| 2, TE | yes | 132 | 3.67 | 5.22 | **+1.55 (se 0.43)** | **2.29** |
| 2, WR | yes | 512 | 4.37 | 5.08 | +0.71 (se 0.29) | 0.99 |

Positive in all five seasons (+1.36, +0.24, +0.32, +1.25, +1.75). That is with Friday's report already in the features.
On Sunday-morning news the model has nothing at all: Sadiq stayed at 7.5 in every refresh after Mason Taylor was ruled
out and scored 26.5; Isaiah Williams stayed at 6.6 after Mitchell was out. The crowd priced both (Sadiq was in 21 of
the top 25). The Sunday build removes inactives; it does not add this. **A T-70 redistribution rule** (a share of the
out starter's projected targets or carries to the next same-position player on the depth chart, sized from the table
above) is a model change with historical support and a two-line implementation in the projection step.

### 5.2 The Questionable haircut stays on after activation

In the Week-3 frame, Questionable players were served at about 0.82–0.87 of the 0.45/0.55 blend (healthy players sit
at 1.04 of it), so the haircut was live at roughly ×0.80. The ten Questionable players with a market price and a score:

| player | pos | served | market | actual | field ownership |
|---|---|---:|---:|---:|---:|
| Jaylen Warren | RB | 12.2 | 15.1 | **23.6** | 13.1% |
| Zay Flowers | WR | 12.2 | 15.9 | **15.4** | 0.6% |
| Jalen Coker | WR | 10.1 | 13.5 | 3.8 | 11.6% |
| Mike Evans | WR | 11.4 | 12.9 | **12.4** | 1.1% |
| DJ Moore | WR | 8.4 | 11.0 | **12.7** | 1.9% |
| Brock Bowers | TE | 8.1 | 11.1 | **30.6** | 0.7% |
| Pittman, Mitchell, Spears, Legette | | 22.5 | 22.3 | 4.1 | |
| **all ten** | | **84.9** | **101.8** | **102.6** | |

The market was right; the haircut removed 17% of a group that scored its market projection, and the flag rule kept
every one of them out of the protected ranks. Bowers scored 30.6 at 0.7% ownership. Historically (my 09-24 analysis,
2018–25): Questionable players play 72% of the time; when they play they score 0.87–0.90 of a healthy player relative to
projection; and they are owned 30–60% less than comparable healthy players. The haircut is right for a late-game player
whose status is unknown at the 11:15 upload (expected value about 0.72 × 0.9) and wrong for a player declared active at
10:30 (0.9, and the market already carries it). **Rule:** at T-70, a Questionable player who is active takes the blend
without the haircut; a late-game Questionable player keeps it; the flag rule applies to late-game players only (the
live re-layout built on Thursday already reads live DK status, so this is a one-line change to what it flags).

### 5.3 Late-game inactives

Announced about 1:35–1:55 CT, after the upload. Replacing them in every entry is operations, not research (the laptop's
words); the ESPN points feed validated on Sunday is the input. This should be built regardless of what L11 says about
score-based late swap.

---

## 6. The pool is built for the wrong objective

The lev generator maximizes the tournament valuation, which values every sub-$4k skill player at about his 90th
percentile (Week 3: 244 such players, valued 6.6 points above their mean; 20 of them with a mean under 1 and a valuation
of 8+). The boom generator solves per-world optima. Neither maximizes the projected mean, which is what the mean track
then selects on.

**Week 3, the frame that was built on Saturday** (house rules, cap 4, $49k floor, overlap ≤ 7 between rows):

| | projected mean | punts per row | realized (in-sample) | time |
|---|---:|---:|---:|---:|
| frame optimum by mean (one lineup) | 135.0 | 2 | 141.5 | 0 s |
| plain-mean optimizer, 144 diverse rows | **133.3** | 2.0 | 136.5 | **171 s** |
| the pool's best 144 by projected sum (the mean track) | 130.6 | 2.8 | 151.4 | ~10 h build |
| frame optimum by the tournament valuation (what lev maximizes) | 128.5 (valuation 165.9) | 5 | 130.2 | |

The pool's rows are 2.7 projected points below what the frame allows, because the generator was aiming 6.5 points
away from the mean. The realized numbers are one week and both books are in-sample; the pool's 151 came from a core
that hit (one player in 138 of its 144 rows). The structural facts are the projected gap and the build time.

**Historically** (106 slates of 2019 and 2021–25, 40-row books, house rules, overlap ≤ 7, realized points): a plain-mean
optimizer on each slate's frame realized **128.9 per lineup against 120.9** for the best 40 rows of that slate's pool by
mean: **+8.0 (t 5.0), better in all six seasons (+2.4 to +10.8) and on 74 of 106 slates**, with a projected gap of
+7.2 and 1.9 punts per row against 4.0. The historical pools were small (about 240 candidates, all built to the
tournament valuation), so the gap there is larger than the +2.7 projected on the 12,559-row Week-3 pool; the direction
is the same in both. The optimizer's books are more concentrated (spread of the book mean across slates 21 against 17),
which is the exposure question below.

**Concentration.** The mean track's Week-3 book put one player in 96% of rows. Historically a per-player exposure cap
on the mean book costs 1.5 points at 50% and 3.4 at 25%, cuts the across-slate spread of the book mean from 17 to
13–15 points, raises the worst-decile week from 99 to 101–103 and, because it diversifies, raises the best-of-40 from
165 to 170. On Sunday the cap would have cost 14–23 points because the concentrated core hit. That is the trade: a small
expected cost for a much smaller chance of a zero Sunday. With several tickets per user allowed, expected tickets are
unchanged by concentration; only the variance moves. The operator chooses the risk; 50% is the reasonable default.

---

## 7. What the evidence does not support

| item | what was claimed | what I found |
|---|---|---|
| **ownership tilt** (adopted early Monday, reverted) | +5.4 points per row on Week 3 | the figure used realized ownership; with the pre-lock sets the tilt loses 3.3 (the laptop's catch). The field's own lift by ownership is non-monotone within projection bands; L12 is the honest test |
| **market floor** (Q6) | +3.5 / +7.1 residual where we sit ≥1 below the market | on 4,926 historical player-weeks with a price: the model-below-market group's residual is +1.4 against a +0.6 baseline, and the floor's MAE is 5.833 against 5.826 without it. Not a lever |
| **MAXGAME5 / QB+3** | 2–4× field lift | L10: −1.6% tickets, not flip-eligible; the field lift does not carry into our pipeline |
| **simulated P(≥line) selection** (the tail sleeve; L09's PL arms) | the right satellite objective | on the Week-3 pool the P(≥175/190/205) books realized 123–125 against the mean track's 151 and were worse at every real line; L09: +0.3–1.9% over MEAN at p89, under the bar |
| **the corrected-hsim selection bank** | half of the dual-law worlds | its per-player mean shifts (the four largest, +3.1 to +3.5: McMillan, Achane and Taylor busted, Smith-Njigba boomed) had correlation −0.04 with Sunday's residuals; its MAE was 5.48 against 5.33 for the served mean; ranking the pool by it gave 122 against 151 by the plain projection. One week; worth a preregistered check, since EMAX selects on it |
| **the Sunday build alone** | Sunday beats Saturday | true both weeks, and mostly from removing inactives; the beneficiaries stay flat (§5.1). Timing without the model rules is half the gain |
| **exposure caps on the mean track** | cheap insurance | a real cost in expectation (§6); the operator's risk choice, not a free lunch |
| **the punt valuation for the satellite pool** | a deliberate lottery from the research panels | those panels measured the tail; for tickets at p91–p99 the plain mean is the target, and a plain-mean build has fewer punts and a higher projected mean (§6) |

---

## 8. The entry order, and the lesson

My 09-24 replay measured "fewest predicted LOW first, then greedy" at +2.6 points on the shared head across 107
historical books, with the head's realized mean varying by ±15 from week to week. The operator adopted it within a day;
on Sunday it pushed the book's best row out of the head. The post-mortem measured the entered order's rank correlation
with the outcome at −0.001, which is what a +2.6 average with that much noise looks like on one draw. Two things follow:
- **a selection or ordering change should run one paper week before it touches an entered book**, whatever the replay
  says; the cash-shadow arms that would have shown this were never built (production's own finding);
- under the mean track the order is by projected mean, and this order is retired. Its replay stands as a record.

The same applies, in the other direction, to the mean track: the +31 points on Week 3 is in-sample; the historical
expectation is +2.9 points per lineup and +13–21% tickets at the 89th percentile, lumpy week to week (L09/L10).

---

## 9. The changes, in order

Everything here is a nomination to the operator. Each carries its test and its earliest safe week.

| # | change | evidence | test before entry | earliest |
|---|---|---|---|---|
| 1 | **Measure and select at each contest's real line.** Every read (L09/L10 successors, Monday scoring, the rehearsal) reports tickets at the contest's own line from its ladder, including the 99th-percentile lines; `contests.json` carries the line percentile; the "mean" track is only for contests whose line is at or below the 96th percentile | §2 | none; it is measurement | Week 4 |
| 2 | **A field-class selector for the 99th-percentile contests and the Millionaire seats**, replacing the simulator's P(≥210) sleeve. Fit each Monday on all settled fields to date (shape only, pre-lock safe); score the pool; take the top rows under the overlap cap. Run as a **paper track for Weeks 4–6** beside the mean track, scored at real lines | §4 | preregister now: adopt for entry only if its paper tickets at the real lines beat the mean track's in ≥2 of 3 weeks and its book mean is not worse | paper Week 4; entry Week 7 at the earliest |
| 3 | **T-70 model rules:** (a) redistribute an out starter's projected volume to the next same-position player; (b) drop the haircut for Questionable players declared active, keep it for late games; (c) flag only late-game Questionable rows | §5 | (a) walk-forward on the replay panel with the depth charts (the table in §5.1 is the census); (b)/(c) the historical 09-24 tables and Sunday's ten players; all three on the Week-4 paper build | paper Week 4; entry Week 5 |
| 4 | **Late-game inactive replacement** for every entry after 1:55 CT, from the ESPN feed and the frozen-map swap machinery | §5.3 | correctness tests and a dress rehearsal on Thursday night's game | Week 4 |
| 5 | **Build the satellite pool with a plain-mean optimizer** (house rules, cap 4, $49k floor, overlap ≤ 7, a per-player exposure target the operator sets, MIN_PROJ) and drop the lev batch from the satellite build; keep boom + the class selector for the tail contests | §6 | the historical 107-slate comparison (§6); a Week-4 paper book beside the pool's mean track, scored at real lines | paper Week 4; entry Week 5 |
| 6 | **Contest selection from the table**, weekly: no $2 satellites unless the paper book averages 160+; the FFWC qualifier and 2,378-entry supersats treated as tail contests (item 2); the 594-entry supersats are the softest per line | §2 | none; the operator's allocation | Week 4 |
| 7 | **Stake:** minimum entries until a paper ticket rate above break-even (1.10–1.19× the field's) is measured for three consecutive weeks per contest type | §2 | the Monday per-type report | Week 4 |
| 8 | **One paper week before any selection, ordering or construction change reaches an entered book**, with the cash-shadow / paper arms built into the arm-timer chain, not a human's evening list | §8 | | standing rule |
| 9 | **Preregister a check of the corrected-hsim selection bank** against the incumbent bank alone (EMAX on each, tickets at real lines and the Millionaire share) | §7 | a lab panel; local hosts | when the workstation is free |
| 10 | **Keep, as decided:** the Sunday 09:10 build with the T-70 re-selection fallback, MIN_PROJ, the DST cap, `MAX_PER_GAME=4`, the lag ownership sets, O1 (FP ownership capture), L11/L12 reads, the vendor capture order, the Monday field report | | | |

**What to stop:** the fewest-LOW order (done); the simulator tail sleeve as the Millionaire selector; measuring
satellites at 149.5 or at p89 only; adopting any lever on a number that has not been reproduced with pre-lock inputs
(the laptop's rule 2); adding entry-path switches without a paper week.

---

## 10. Risks

- **Too many simultaneous changes on the money path.** Week 4 already carries the mean selector, the tail sleeve, the
  layout tracks, the Sunday build, MIN_PROJ, the DST cap, lazy cuts, the live re-layout and the frozen-map swaps, on a
  laptop that becomes the only host on Tuesday. Week 2 was lost to defects, not strategy. Items 3–5 above go in as
  **paper arms** first for that reason; item 2 is paper by design.
- **The class model leans on our projection percentile.** In a week like Week 2 it fails with the projection. The
  fail-loud audit (non-players, availability) is the guard; the model should also refuse to score a pool whose
  projection fails the audit.
- **Two test weeks** for the class model; **one week** for the hsim finding; **in-sample** for every Week-3 pool number.
  The paper weeks are the evidence, and the document says so wherever a number is in-sample.
- **Concentration** is the operator's risk choice, and the mean track as adopted has none of it capped except the DST.
- **The field data is the asset.** Every table in §2 and §4 came from `contest_entries`, which nothing on the money path
  reads. A Monday refit of the class model and the per-type ticket table should be a fixed step of settlement.

---

## 11. Reproduction

`reports/lab-handoffs/2026-09-28-week3-review/README.md`. The scripts read the warehouse (read-only), the archived
Week-3 run dir in the private bucket, the public contest ladders, and the 107-slate test bed of the 09-24 review. The
laptop's `milly_shape_lift.py` (integration) supplies the field features. Data stays outside the repo; standings carry
user names.
