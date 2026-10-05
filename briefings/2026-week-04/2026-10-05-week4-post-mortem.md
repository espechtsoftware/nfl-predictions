<!-- Repo copy. No user names, entry ids or dollar amounts; the stake and dollar counterfactuals stay in
     ~/week4-sunday/private/. Every points-based number here is reproducible from the files named in §10. -->

# Week 4 post-mortem: what happened, where the points went, and whether our selection helps

Written 2026-10-04/05 by the laptop agent for the operator. The reviewer has checked the selection section (§2). Every
number comes from:
- the 26 final standings files;
- the pre-lock DK entries export (154 entries);
- the T-70 projection batch `2026-10-04 15:40:30.984911 UTC`;
- the Sunday pools;
- the warehouse.

## 0. The result in one table

| | |
|---|---|
| Entries | 154 in 26 contests (152 from the bundle, 2 added by hand) |
| Cashes | 3: the hand-added Millionaire seat (182.58, rank 1,647 of 161,764, 99.0th percentile, 0.2 short of the top 1%) and the same 148.78 lineup in two 118-entry 25x supersats |
| Return (settled; DK entry history 10-04 20:18) | **0.42× fees** counting the two supersat tickets at face; 0.27× in cash. Amounts are in the private copy |
| Average entry | projected 135.4, scored 115.6 (−19.7) |
| Median finish | 42.6th percentile (the field is 50) |
| Best book lineup | 162.42; the Millionaire winner scored 234.2 |

**In one paragraph.** One game decided the slate: DAL–HOU scored the most DK points (227), and we had no player from
it. Four heavily used players busted at once: Parker Washington, Chase (in-game concussion), Garrett Wilson and
Lawrence. Together they cost 4,228 points, more than the whole net shortfall. Our book was much chalkier than the
field (ownership sum 152% vs 110%) and concentrated in three games. Measured fairly, our lineup selection was no
better than random picks from our own pool:
- Week 4: below the median random book;
- Weeks 1–4 together: indistinguishable from random (72nd percentile; above the median in 50 of 86 contests); Weeks 1–2 above, Weeks 3–4 below;
- the pool itself beat fully random legal lineups clearly.

The value we add is in the pool, and the selection step has not yet shown it adds anything. The operator's "a
monkey could have chosen better" is half right: a monkey picking from OUR pool would have done about as well, and
this week slightly better; a monkey picking from the whole slate would have done worse.

## 1. Where the points went

**The deciding game.** DAL–HOU: pre-lock total 48.5 (tied 3rd of 12), 227 DK points (1st). Our book put 0.00 slots
per lineup there. 70 of the Millionaire's top 100 lineups were built mainly on it. The field's DAL–HOU owners were
rewarded, as these ownership vs DK points figures show:

| Player | Field ownership | DK points |
|---|---|---|
| Lamb | 10.2% | 44.3 |
| Collins | 12.2% | 33.8 |
| Stroud | 5.9% | 26.1 |
| Prescott | 5.2% | 21.1 |

- Our pre-lock projections had Stroud 19.4 and Prescott 19.3, both ABOVE the market. So the model did not dislike
  the game.
- DAL–HOU players sat in 31–35% of pool rows; the selection step left them out.
- With hindsight, pool rows holding 3+ of them averaged 135.2, vs 115.3 for rows with none.

**Where our slots went.** About 6 of 8 skill slots per entry sat in three games:
- CIN@JAX 2.76 slots (field 1.29);
- MIA@MIN 1.71 (the slate's LOWEST total, 38.5; it finished last, 114);
- ARI@NYG 1.49.

The four games that beat their projections most held 0.43 of our slots, vs the field's 2.10:

| Game | Over projection |
|---|---|
| KC@LV | +41 |
| DAL@HOU | +40 |
| BUF@NE | +25 |
| BAL@TEN | +20 |

**The busts** (points lost vs projection across all our entries):

| Player | Entries | Our proj | Market | Actual | Points lost | Note |
|---|---|---|---|---|---|---|
| P. Washington | 95 | 16.06 | 15.63 | 2.0 | −1,336 | below his p10; nobody on JAX absorbed his role |
| Chase | 75 | 20.62 | 18.35 | 5.7 | −1,119 | in-game concussion; no pre-game designation |
| G. Wilson | 83 | 18.06 | 16.89 | 5.7 | −1,026 | the whole NYJ offense failed (−54 vs projection); lowest implied total of our heavy plays (20.0), visible pre-game |
| Lawrence | 92 | 21.20 | 19.14 | 13.08 | −747 | |
| Addison, Love, McCaffrey, McBride | | | | | −428, −346, −335, −314 | McCaffrey (95 entries) was a mild miss, not the cause |

- **Offsets:** Hockenson +1,524, Walker +676, Strange +672.
- **We sat above the market** on Chase (+2.3), Lawrence (+2.1) and Wilson (+1.2): the wrong side, all three.
- **Where those players' points went:**
  - CIN's offense finished +21.6 over projection without Chase: Higgins 29.7, D. Meyers 15.2, Burrow 28.7. We held
    Higgins in 11.7% of entries and Burrow in 1.3%.
  - JAX finished −16.5: Strange +7.3 was the only gainer.
  - SF: Deebo Samuel 18.0 and Kittle 17.0 beat McCaffrey's 16.0.

**What the usage data shows** (nflverse weekly stats for Week 4, loaded Monday 10-05):

| Team | Pass attempts | Our heavy plays | Where the volume went |
|---|---|---|---|
| **JAX** | **Lawrence 23 (227 yds)** | P. Washington: **3 targets**, 1 catch, 7 yds; Lawrence 13.1 DK | Run-heavy script: Tuten 17 carries, Rodriguez 6 (1 TD). In the pass game, Strange took 8 targets (35% share, 95 yds) |
| **NYJ** | **Geno Smith 15 (119 yds)** | G. Wilson: 4 targets, 27 yds | Nowhere: the whole pass offense disappeared (I. Williams 3 targets, 73 yds, 1 TD) |
| **CIN** | **Burrow 54 (428 yds)** | Chase: 3 targets before the concussion | Higgins **16 targets, 157 yds**; Chase Brown 11 targets; D. Meyers 9; Tinsley 7. The points stayed in CIN's pass game: our bring-back side was right, and the receiver who exited was the one we held |
| SF | Purdy 30 | McCaffrey: 15 carries + 5 targets, 1 TD (16.0 DK) | Normal usage: a mild miss, not a role change. Evans 8 targets, Kittle 6 (1 TD) |
| MIN | Murray 37 | Addison: 6 targets, 52 yds | Hockenson **13 targets, 13 catches, 119 yds** (39% share) |
| ARI | Brissett 35 | McBride 12 targets (34%) but 31 yds; Love 14 carries, 63 yds | McBride's volume was fine and his efficiency was not. Allgeier's TD took the scoring |
| DAL–HOU | Prescott 45 / Stroud 31 | none (0 exposure) | **Lamb 21 targets (49% share), 189 yds**; Collins 8 targets, 118 yds, 2 TD; Stroud 347 yds, 2 TD; Javonte Williams 19 carries, 3 TD |

**The reading:**
1. **Our two worst stacks (JAX, NYJ) died of passing-VOLUME collapse** (23 and 15 attempts), not of targets going to
   someone else.
2. **That is game-script risk.** It hits a QB and all his receivers at once, which is exactly why concentration
   multiplied it. Half the book on one QB's passing volume is one coin.
3. **Chase's exit shifted volume to teammates we barely held** (Higgins 11.7% of entries).
4. **McCaffrey and McBride were usage-normal misses.**


## 2. Did our selection help? The monkey benchmark

The reviewer's design, run on all four weeks. Week 2's pool was found archived on 10-04, and its 12 payout ladders
were fetched from DraftKings' public contest data.

Each comparator is 1,000 books, scored at each contest's own paid line:
- **M2 (the fair comparator):** random rows from our own pool, dealt into contests under our caps and layout.
- **M1:** random pool rows drawn independently per contest.
- **M3:** random legal DK lineups from the whole slate.

Percentiles are mid-rank: ties count half.

**Book level, on cashes (our percentile among the monkey books):**

| Week | M1 | M2 | M3 | Pool skill: projected vs realized rank corr., lineups (players) | Note |
|---|---|---|---|---|---|
| 1 | 86.4 | 98.6 | 100 | 0.33 (0.69) | 18 cashes vs a median of 12 for M2 |
| 2 | 84.0 | 81.3 | 65.3 | **−0.49** (0.58) | 3 cashes vs a median of 2; the pool's highest-projected lineups shared a core that busted together |
| 3 | 22.4 | 34.0 | 79.0 | 0.32 (0.73) | |
| 4 | 8.7 | **22.9** | 57.4 | 0.06 | 3 cashes vs a median of 6 |
| **1–4 combined** | 58.9 | **72.2** | 100 | | | 25 cashes vs a median of 21.5 for M2; each monkey book summed across weeks, so weeks weigh by entries |

**Contest level, on score:** in each contest, is our total above the median random book's?

| Week | vs M2: above / below | vs M3: above / below |
|---|---|---|
| 1 | 3 / 0 | 3 / 0 |
| 3 | 29 / 16 | 33 / 12 |
| 4 | **7 / 19** (p 0.03) | 22 / 4 |
| **1–4** | **50 / 36** (p 0.16) | **66 / 20** (p < 0.001) |

**Caveats:**
- Contests share lineups, so they are not independent and the p-values are optimistic.
- Week 3's M3 has 29% of its lineups touching players nobody drafted (scored 0), which flatters us against M3 in
  that week only.
- Week 2's actuals are complete: DraftKings' own scoring for 343 players, the warehouse for 83 (it matches DK exactly
  on all 317 players in both), and 3 who did not play.

**Reading:**
1. **The pool is good.** Against random legal lineups we win 66 of 86 contests.
2. **The selection on top of the pool is indistinguishable from random over four weeks:** 72nd percentile, and 50
   of 86 contests above the median.
3. **The pattern by week:** Weeks 1–2 were well above random, Weeks 3–4 below. That coincides with the selection and
   construction changes made for Week 3 (the mean selector, the union of pools, the head layout).
   **This is a hypothesis for Friday's money gate, not a finding:** two weeks on each side cannot separate a change
   from luck.
   - **It also coincides with the pool's projection skill** (the skill column; reviewer's note). In Week 2 our
     selection beat random although the pool's projected order ran backwards. In Week 4 the projected order carried
     almost nothing.
   - **Friday's primary comparison is the CURRENT system against M2 on Weeks 1–4,** with the per-contest sign test.
     A "return to the Week 1–2 construction" would need its own preregistered arm. Choosing it because Weeks 1–2
     looked better would be choosing on the weeks it is scored on.

**What the layers did** (average realized score by source, Week 4):

| Source | Average |
|---|---|
| The pool's top 105 by projected mean | 121.9 (84.8% at ≥100) |
| Sunday pool, random row | 119.7 |
| T-70 pool, random row | 116.8 |
| **The optimizer rows we entered** (projection + 0.20 × predicted ownership) | **115.8** |
| Field-sleeve rows | 114.9 |
| Plain-optimizer control rows (same optimizer, no ownership term) | 111.7 |

So **the ownership term helped** (+4.1 over the plain optimizer). The gap to random pool rows comes from the capped
sequential optimizer and the concentration it produces:
- 8 players sat exactly at the 52-row cap;
- 97% of the book used three QBs: JAX 92 entries, ARI 45, MIN 13;
- 133 entries held McCaffrey, Chase or the JAX QB, and 37 held all three.

The simplest alternative, "the pool's top rows by projected mean, under the caps", is an arm in Friday's money gate.

**Ranking signal:**
- Inside the pool, projected vs realized rank correlation was 0.06 this week (W1 0.33, W3 0.32).
- Inside the book, the top-ranked rows did slightly worse (+0.15 rank correlation, i.e. the wrong way).

## 3. Could the pool have won?

**Millionaire cut lines:**

| Place | Score |
|---|---|
| 1st | 234.2 |
| 10th | 225.8 |
| 100th | 209.2 |
| 1,000th | 188.2 |

- **None of the top 100 is in our pool.** The closest pool row shares 5 of 9 players with 63 of them, 6 with 24, and
  7 with 4. No pool row shares 7+ players with any top-10 lineup.
- **The pool's upside was thin:** 4 rows scored ≥209.2, 76 scored ≥188.2, and the best scored 211.8.
- **Our best entries:** 182.58 overall (the hand-added Millionaire seat); 162.42 from the book.

So in Week 4 the pool could reach the top 1,000 but not the top 100, and the selection step did not find even the
pool's good rows. Week 3 had the same pool ceiling problem (best 207).

## 4. Concentration and the Chase injury (study 4)

**Exposure:** 75/154 entries (48.7%) held Chase, vs the field's 19.5% (2.5×). 51 of the 75 paired him with Lawrence +
P. Washington as the bring-back.

**Damage:** Chase entries averaged 108.2 vs 122.7 for the rest, a gap of 14.5 that matches his 14.9-point miss.

**Counterfactual** (replace his 5.7 with):

| Chase scored | Cashes, fixed lines (actual 3) | Cashes, field-adjusted lines |
|---|---|---|
| His mean, 20.6 | 4 | 4 |
| p75 proxy, 33.2 | 8 | 5 |
| p90, 40.2 | 12 | 7 |

Even at his projection, Chase lineups would have finished about 52 points short of their cash lines.

**Not foreseeable:** no injury designation, an in-game concussion. **In our control:**
1. **Concentration.** At 2.5× the field, one in-game event touched half the book. The field's top-1% held Chase only
   3.5% of the time.
2. **The bring-back choice.** CIN's points went to Higgins and Burrow.

This is study 1's question (the entry-level exposure cap, with the P4 offset-dealing arm), to be preregistered for
Weeks 5–6.

**Other counterfactuals** (named players at their projection, the field held fixed; actual 3 cashes):

| Players at projection | Cashes |
|---|---|
| Washington | 6 |
| JAX stack | 6 |
| Wilson | 5 |
| Chase | 4 |
| McCaffrey | 3 |
| Washington + Chase + Wilson | 16 |

## 5. Matchup difficulty: "Why McCaffrey against a good defense like Denver?"

This section is descriptive: it is not the preregistered study 11(b), and nothing here is an adoption claim.

**Short answer:**
- **The criticism is right about the model.** It has no direct run-defence term.
- **It is mostly wrong about the cost.** The betting market already prices matchup difficulty, and our served projection
  is 55% market.
- **Denver was not a good run defence in 2026.**

**How a "good defence" reaches a projection today** (checked in the code):
1. **The prop market, at 55% weight.** 120 of the 121 Week-4 players projected at 8+ had prop lines.
2. **Inside the model:** implied team total, spread, game total and expected script.
3. **Explicit defence features:** pass coverage only (`cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`,
   `db_ypt_allowed_l6`, `top_cb_out`).

Run-defence and points-allowed-by-position measures exist in the warehouse but are in no model list:
- `epa_per_rush_allowed_l6`;
- `{qb,rb,wr,te}_fp_allowed_adj_l6`;
- `opp_pressure_rate_l6`.

(Ledger correction: Addendum 8's "trailing defence-vs-position form" is not in the current model.)

**Is there signal beyond the market?** A point-in-time defence-vs-position (DvP) measure was built:
- DK points allowed by position, adjusted for the opponents faced;
- windows ending the week before;
- early weeks blended with the prior season at a fixed 6-game weight, not tuned.

| Measured against | Seasons | Easiest − toughest fifth of matchups, DK points (95% CI) |
|---|---|---|
| A naive trailing average | 2018–25 | **+1.33** (1.00 to 1.58): matchups matter |
| A walk-forward model on our features | 2018–25 | +0.74 (0.50 to 0.94) |
| **The prop market** | 2023–25 | **+0.02** (−0.58 to +0.68): the market prices it |
| **An approximation of what we serve** (45% model, 55% props) | 2023–25 | **+0.18** (−0.42 to +0.84) |
| Our actual served projections | 2026 W1–4 (674 player-weeks) | +0.40, slope interval −0.14 to +0.43 |

- **The full DvP adjustment on top of the served approximation makes error worse** in every season (MAE 5.60 → 5.70).
- **In 2026, running backs facing tough matchups BEAT their projections.**
- **Where something small may remain:** RBs (slope +0.14, interval −0.08 to +0.37) and the upside tail (boom rate +2.1
  points easiest vs toughest fifth, interval −0.2 to +4.6). Even if real, it is about 0.05–0.1 DK points per player.

**McCaffrey vs Denver:**
- **Denver's run defence:**
  - **2025:** fewest RB points allowed (rank 1 of 32).
  - **2026 Weeks 1–3:** 29.7 RB DK points allowed per game (rank 27), and 32nd in rush EPA allowed.
  - **Blended:** about average, rank 20 after adjusting for opponents faced.
- **The market saw it the same way:** his prop-market number at T-70 was 20.36, ABOVE our model's 18.5, so the served
  19.5 sat between them. SF's implied total was 25.75 (joint 6th of the slate).
- **A matchup adjustment would have moved him UP slightly** (+0.6 full, +0.1 at the size history supports). Only a
  "2025 reputation" view cuts him, and last season alone adds nothing beyond the market.
- **He scored 16.0,** a mild miss inside his range. The defensible criticism of McCaffrey is concentration: 62% of
  entries vs 28% field ownership.

**The other heavy plays:** a full DvP adjustment pointed the right way about half the time.

| Pointed right | Pointed wrong |
|---|---|
| Washington, Addison, McBride, Stroud, Collins | McCaffrey, Lawrence, G. Wilson, Lamb, Prescott, Javonte Williams |

Javonte Williams scored 31.3 against Houston, the toughest RB matchup on the slate. A DvP tilt would have pushed toward
HOU (Stroud, Collins) and away from DAL (Lamb, Prescott). **It would not have fixed the zero DAL–HOU exposure; that was
a selection and concentration problem (§2, §6).**

**Study 11(b), proposed for preregistration:**
- **Residual target:** a frozen walk-forward replay of the full served stack on 2023–25 (props exist), plus 2026 Weeks
  5–18 read prospectively.
- **The measure:** one pre-specified DvP measure (opponent-adjusted, 6-game prior blend). Secondary, RB only: rush EPA
  allowed.
- **Primary:** the pooled slope, clustered by week, must be positive with its interval above 0, in at least 2 of 3
  seasons, with the 2026 sign agreeing.
- **Practical gate:** ≥ 0.03 MAE improvement, or a ≥ 2-point boom-rate gap.
- **Multiple testing:** positions only through a Holm hierarchy, RB first.
- **Pass route:** a paired calibration shadow (adoption track class C).
- **Cheaper alternative:** a model-side `EXTRA_FEATURES` candidate.
- **Expected lineup-level effect if it passes:** small, about 0.05–0.1 points per player.

## 6. What the winners built (Millionaire, 161,764 entries)

**How the comparison was checked:**
- **Definitions:** they reproduce Week 3's published table within about 1 point. In that table "QB+2" means 2+ WR/TE
  teammates.
- **Coverage:** 161,516 lineups parsed; 248 empty lineup strings left out.
- **Scoring:** recomputed points match DK to within 3e-5.
- **Our column:** all 154 entries (93 distinct lineups), weighted by entries as in Week 3.
- **Ownership:** the final, post-lock %Drafted.

| | Milly top 10 | top 100 | top 1000 | field | OUR 154 |
|---|---:|---:|---:|---:|---:|
| Points | 229.3 | 216.0 | 197.6 | 118.5 | 115.6 |
| QB salary | $5,790 | $5,829 | $5,884 | $5,901 | $5,611 |
| QB under $5,500 | 20% | 10% | 16% | 29% | 38% |
| QB+2 stack (2+ WR/TE) | 0% | 14% | 23% | 32% | 99% |
| Bring-back | 80% | 75% | 66% | 45% | 99% |
| Max players from one game | 3.00 | 3.08 | 3.15 | 3.10 | 3.99 |
| Ownership sum (chalkiness) | 94 | 99 | 100 | 110 | **152** |
| TE salary | $3,620 | $3,527 | $3,776 | $4,467 | $4,235 |
| TE in FLEX | 60% | 40% | 41% | 35% | 61% |
| RB salary (2 slots) | $12,370 | $12,358 | $12,422 | $12,890 | $13,249 |
| WR salary (3 slots) | $20,050 | $20,187 | $19,639 | $18,083 | $18,750 |
| WR in FLEX | 30% | 34% | 35% | 35% | 8% |
| Distinct games per lineup | 5.40 | 5.57 | 5.65 | 5.82 | 4.94 |
| ≥1 player from DAL–HOU | 100% | 99% | 91% | 39% | **0%** |
| QB from DAL–HOU | 80% | 82% | 64% | 11% | 0% |
| ≥3 players from JAX–CIN | 0% | 1% | 9% | 19% | **61%** |

**Pre-lock totals:**

| Game | Total |
|---|---|
| JAX–CIN | 51.5 (highest) |
| NE–BUF | 49.5 |
| DAL–HOU | 48.5 |
| DEN–SF | 48.5 |

**The top 100:**
- **Built around one game:** 78 built mainly on DAL–HOU; 82 took their QB from it (Stroud 63, Prescott 19).
- **Most-used players** (top-100 share / field share):

  | Player | Top 100 | Field |
  |---|---|---|
  | Collins | 90% | 12% |
  | Lamb | 87% | 10% |
  | Hockenson ($3,300 TE) | 66% | 16% |
  | Stroud | 63% | 6% |
  | Kyren Williams | 60% | 9% |

- **Most common triple:** Stroud + Lamb + Collins, 53 lineups (1.1% of the field).
- **Our most common triple:** Lawrence + P. Washington + Strange, 90 of 154 entries (4.3% of the field).

**Stack shapes:**

| | Most common shapes |
|---|---|
| Top 100 | QB + 1 receiver + 1 bring-back: 55; QB + 1 receiver, no bring-back: 19; QB + 2 receivers + bring-back: 10; naked QB: 5 |
| Ours | QB + 2 receivers + bring-back in 153 of 154. **Our construction rules cannot produce the week's most common winning shape.** |

**Week 3's lessons did not hold in Week 4.**

| Week-3 pattern | Week 4 | Held? |
|---|---|---|
| Cheap QB | Under $5,500 in 10% of the top 100 vs 29% of the field | No |
| QB+2 | 14% vs 32% | No |
| 4 players from one game | 3.08 vs the field's 3.10 | No |
| Chalkier than the field | 99 vs 110: winners were less chalky | No |
| Bring-back | 75% vs 45% | Yes |
| Cheap TE | $3,527 vs $4,467, mostly Hockenson | Yes |
| Heavier WR spending | $20.2k vs $18.1k | Yes |

**We moved toward Week 3's shape and overshot on chalk:**
- QB salary went down ($5,948 → $5,611).
- TE in FLEX went up (52% → 61%).
- WR spending went up ($17.2k → $18.8k).
- **The ownership sum jumped from 86 to 152**, in a week when the winners were contrarian.

**Changing construction rules from either week alone would be fitting to one slate.** Only the bring-back, cheap TE and
WR-spend patterns appear in both weeks.

**Duplication.** The field is mostly unique: 156,006 distinct lineups of 161,516. Ours was not:
- Our 154 entries hold 93 distinct lineups, reused across contests.
- 32 of the 93 were built identically by other users in the Millionaire: 148 entries from 138 users. One of our
  lineups was built by 44 other users.
- Those were the obvious chalk builds, and they scored poorly: the best copy of the most-duplicated one finished near
  rank 140,000.
- The top 1,000 almost never duplicated each other (982 distinct).

## 7. Past winners and top scorers this week

Groups come from the Weeks 1–3 Millionaires:
- the 3 weekly winners;
- 551 users with top-1% finishes in 2+ weeks;
- each week's top-100 users.

"Matched" = the field rate for users with the same number of Week-4 entries.

| Group | Users in W4 | Top-1% rate (matched) | Cash rate (matched) |
|---|---|---|---|
| W1–3 winners | 3 | 0.63% (1.32) | 29.1% (27.5) |
| Repeat top-1% | 498 | 1.29% (1.31) | 27.2% (26.5) |
| Union of all groups | 633 | 1.29% (1.31) | 27.1% (26.4) |
| Whole field | 54,720 | 1.00% | 23.2% |

- **Persistence:** 4,238 users had a top-1% finish in Weeks 1–3; 377 of them had one in Week 4, vs 370 expected from
  entry counts alone.
- **Past winners performed exactly as their volume predicts.** They did not "all do horribly", and they did not repeat
  either. This matches the winners study (winners lose 83% of other weeks).
- **Chase:** the past winners held him in 23.4% of entries, above the field's 19.5% and far below our 48.7%.

## 8. Corrections to what was said on Sunday night

- **"Our selection was worse than random" was overstated.** The fair comparator (M2) puts Week 4 at the 22.9th
  percentile and Weeks 1–4 at the 72nd; across the four weeks it is above the median random book in 50 of 86 contests (§2).
- **"The extra layers made it worse" was wrong for the ownership term.** It added +4.1 per lineup over the plain
  optimizer. The loss came from the capped optimizer and concentration.
- **Pre-lock numbers:** SF–DEN was a 48.5 total, not 47.5 (KC–LV was the 47.5 game).
- **McCaffrey's market number:** Sunday night's "correction" to 20.15 was itself wrong. The served T-70 batch's
  `market_source_log` row (`2026-10-04 15:40:19Z`) has 20.36 (prop market; our model 18.51; served 19.53), so the
  original "20.4" was right.
- **The suspected "row shift" between the entry plan and DraftKings was an indexing mix-up in the analysis, not a
  defect.** All 24 bundle contests match the plan exactly; the only differences are the operator's 2 hand entries.

## 9. What this changes (candidates; the operator decides, nothing touches the money path untested)

1. **Friday's Week-5 money gate** tests the hypotheses this post-mortem raises on Weeks 1–4 before any stake decision:
   - the selection step vs the monkey (M2) vs "top rows by projected mean under the caps";
   - P&L beside the monkey percentile;
   - walk-forward models and archived pre-lock batches only.
2. **Study 1 + P4** (exposure cap, offset dealing) is the concentration answer. Preregister for Weeks 5–6.
3. **Study 11(b)** (a point-in-time matchup-strength residual test): design in §5. Preregister before reading outcomes.
   Expect a small effect: the market already prices most of matchup difficulty.
4. **Construction shape:** our rules force QB+2 plus a bring-back (99% of the book), a shape 10–14% of the Week-4 top
   100 used. Whether to allow QB+1 plus a bring-back is a candidate arm for the money gate, measured on Weeks 1–4 and
   the history. It is never changed from one week's winners: Weeks 3 and 4 point in opposite directions.
5. **Chalk and duplication:** an ownership sum of 152 against the field's 110, and a third of our distinct lineups
   duplicated in the field. The ownership TERM helped (§2); the concentration from the caps and repeats did not. This
   is study 1 and P8 (field- and duplication-aware EV).
6. **Game coverage:** Weeks 3 and 4 were both decided by a game we under-held. Whether a "minimum exposure to every
   high-total game" rule helps is a P3/money-gate arm candidate, tested on Weeks 1–4 first, never entered untested.

## 10. Files

**Analysis code and outputs** (not tracked; preserved 10-05 from the nondurable scratch to `~/private/pm-week4/` on the laptop,
private because some of it handles DK user names). The monkey benchmark is now the permanent `scripts/moneygate_monkeys.py`
(money-gate harness branch):
- `pm-selection/`: monkey code, seeds, per-contest CSVs, `per_contest_paired.csv`, `per_contest_sign_summary.csv`;
- `pm-players/`: the Chase, points-flow and past-winners work;
- `pm-matchup/`;
- `pm-structure/`.

**Seeds:**
- W4 monkey: 20261004;
- W1: 20260913;
- W3: 20260927;
- W2 (M3 only): 20260920.

**Private inputs** (never committed): `~/week4-sunday/ENTERED/standings/` (26 files),
`~/week4-sunday/private/DKEntries_PreLockWeek4.csv`.

## 11. Follow-up research done since (2026-10-05)

| Question | Answer | Report |
|---|---|---|
| Would today's system have made money over Weeks 1–4? | No: 0.48× fees (0.36–0.67). Better than random picks from its own pools overall (W1–2 well above, W3–4 below). No tested change does better | `briefings/2026-week-04/2026-10-05-week5-money-gate-result.md` |
| In which contest types do we have an edge, and how long would it take to see one? | None can be shown. A 15% edge needs hundreds of weeks of money results. Satellites ran below break-even (0.12×), robustly. Our rows sit about 0.15 sd under the Millionaire field | `briefings/2026-week-04/2026-10-05-p1-contest-type-edge.md` |
| Overlays? | None usable on the classic slate in Week 4. The overlays that held were single-game Showdown copies at 1.10–1.36 | `briefings/2026-week-04/2026-10-05-overlay-backtest-week4.md` |
| Contrarian games? | The top-total game is the week's top scorer only 16–19% of the time, but the field is FLATTER than the odds, so the leverage sits in the top total. Our error was size: 61% of entries on one game | `briefings/2026-week-04/2026-10-05-x1-steps-1-2-shootouts-and-field-allocation.md` |
| What would let us win? | A ranked plan: de-concentration first (study 1 + P4, frozen), then the contrarian-game step, projection hygiene (O-22) and stake evidence | `briefings/2026-week-04/2026-10-05-path-to-winning-plan.md`, `reports/2026-10-05-prereg-study1-deconcentration.md` |

## 12. Monday additions (2026-10-05, after the settled imports and the nflverse Week-4 stats)

**The settled data matches Sunday's analysis exactly.**
- All 26 standings files used on Sunday night (9 CSVs, plus 17 zips compared by their contents) are byte-identical to
  the files imported into `nfl_raw.contest_entries` / `contest_ownership` today. So nothing in §§0–11 changes.
- The limit: the files were downloaded Sunday from 19:01 CT, so a DraftKings stat correction issued later is in neither.

**Where the points went, now with usage** (`nfl_raw.weekly_stats`, Week 4 against each player's Weeks 1–3 average;
target share in brackets):

| Team | What happened to our players | Where the volume went |
|---|---|---|
| CIN | Chase: 3 targets (8.3), then left with a concussion | Burrow threw 54 times (34); Higgins 16 targets (7.7) for 26.7 PPR; D. Meyers 9 (2.3); Chase Brown 11 (4.3). The points stayed in the CIN passing game, not with our player |
| JAX | A VOLUME collapse: Lawrence 23 attempts (27), 162 air yards (241); P. Washington 3 targets [0.13] (7.7 [0.30]) | Strange 8 targets [0.35] (3.3 [0.13]), 16.5 PPR; Tuten 17 carries |
| NYJ | G. Wilson 4 targets (9.0) | Pass volume collapsed: Geno Smith 15 attempts (34); Braelon Allen 14 carries (6.3) |
| SF | McCaffrey's usage was normal or up: 15 carries (11.7), 5 targets; 16.0 PPR | Spread across Deebo 18.0, Kittle 17.0, Evans 12.6; Purdy ran 10 times |
| MIN | Addison 6 targets [0.18] (5.3 [0.24]), 9.1 PPR | With Jefferson out, Hockenson took 13 targets [0.39] (4.3 [0.20]) for 24.9, and Aaron Jones 8 targets plus 20 carries |
| ARI | Love 14 carries but 1 target, 6.5 PPR | Allgeier 8 carries and a TD (12.9); M. Wilson 13 targets [0.37] |
| CHI | – | A role change: Monangai 30 carries (10.0), 28.0 PPR; Swift 15 (18.0) |
| DAL/HOU | The game we did not hold | Lamb's spike was a ROLE change: 21 targets [0.49] (8.3 [0.25]) while Pickens fell to 3 (8.3). Collins' day was 2 TDs on 8 targets. Javonte Williams had 19 carries and 3 TDs. Stroud threw only 31 times (40) but for 385 air yards |

**What it says, in plain words:**
- Two of our biggest stacks (JAX, NYJ) lost on VOLUME: the passing games were smaller than in their first three weeks.
- Chase's points went to his teammates.
- McCaffrey was used as expected and simply had a modest day.
- The week's winners came from two role changes (Lamb's target share doubled; Monangai's carries tripled) and from
  touchdowns (Collins, J. Williams).
- None of this was knowable as such before lock. What was knowable was how much of the book sat on the same few
  players (§4). That is the selection-redundancy study now running (study 17; `reports/2026-10-05-prereg-study17-selection-redundancy.md`).

## 13. Was Jacksonville's low passing foreseeable? (the operator's question, 10-05)

**No. Every pre-lock signal pointed the other way.**
- **The market** (the last odds pull, 10-04 14:02Z; the median player props across books):
  - JAX–CIN was the slate's highest total (51.5), with JAX a 2.5-point underdog: a trailing-team, pass-friendly script.
  - Lawrence's pass-yards line was 257.5; P. Washington's was 75.5 receiving yards on 5.5 receptions.
- **CIN's defense, Weeks 1–3** (play-by-play):
  - 9th of 32 against the pass (EPA per dropback −0.035) and 12th against the run (4.2 yards per carry).
  - Opponents passed on 73.2% of plays against CIN, the league's HIGHEST rate, about 47 dropbacks a game.
  - Fantasy Points' defensive pass-rate-over-expected agrees: CIN +3.7, +13.1 and +4.4 points in Weeks 1–3.
  - The data showed CIN as a pass FUNNEL, not a pass-tough, run-weak defense.
- **What actually happened was the game script.** JAX led throughout and won 22–17 (an upset). In the 4th quarter JAX
  ran 10 times and passed 9, while CIN passed 22 times chasing. JAX had 58 offensive plays to CIN's 76.
  - JAX was already run-leaning: a 53% pass rate in Weeks 1–3.
  - The one mild pre-lock flag: the market had Lawrence 2.1 points BELOW our projection (§1).
- **The lesson** is not a missed signal. A stack's volume rides on a game script nobody can call before lock. The
  avoidable part was putting about 60% of the entries on one stack (concentration; study 17).
