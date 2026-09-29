# Do the winners also lose? And what would make our results more consistent

**2026-09-29, for the operator and both agents.** Two questions from the operator:

1. Are the people who place at the top of the Millionaire and the other large contests also losing on a regular basis?
2. Is there a way to score higher in tournaments on a more consistent basis?

**Data.** Every entry in the 60 contests the operator entered in Weeks 1–3 (1,485,591 entries, 230,081 users), each
with its true prize from the contest's public payout ladder. The computed payouts match DraftKings' stated prize pool
in every contest. The armed Week-4 main book was reproduced on the lab's 36 historical slates (2023–24) and matches
the lab's L18 results exactly on every slate, plus a 17-slate 2022 holdout. Scripts:
`reports/lab-handoffs/2026-09-29-winners-study/` (README there). The data stays outside the repo; no user is named and
no figure here is the operator's.

Everything in Part 3 onward is descriptive research on slates the lab has already read. It nominates; it does not adopt.

---

## 0. The answers

1. **Yes. The people at the top lose in about five weeks of six.** Users who placed in the top 100 of a Millionaire lost
   money in 83% of the other weeks they played, typically 58% of that week's stake. For top-10 finishers it is 85%. The
   three $1M winners lost in four of their six other weeks. The 150-entry professionals are profitable in 12% of their
   weeks; their median week loses a third to a half of the stake (§1).
2. **Skill is real, it is modest, and it does not buy consistency.** A player's average lineup score persists from week
   to week. The best fifth of heavy players average about 6 points per lineup above the field and reach every payout
   line 1.2–2.0× as often as the field. They are still profitable in only 18% of weeks (§2).
3. **Our entries in Weeks 2 and 3 were far below that scale:** about 12 points per lineup *below* the field, worse than
   the weakest fifth of heavy players. The armed Week-4 book measures at about the level of the best fifth at the deep
   lines, and close to the field's average at the shallow ones (§3).
4. **The armed book is one concentrated bet per week.** Its average lineup beats the field's by about 2 points, but the
   whole book moves together: its weekly average swings by ±13 points. Half of all weeks the entire book sits below the
   field's average (§3).
5. **The crowd's ownership is the largest lever found, for the level and for the consistency.** Adding realized
   ownership to the optimizer's objective lifts the book from +2 to +6–9 points per lineup over the field, on the panel
   and on a 2022 holdout, and at the larger weights cuts the weeks with nothing from 19% to 3–8%. That uses hindsight.
   Before lock, our own ownership model captures about a quarter of it. The lab's new blend with LineStar captures more
   than half: +4 points per lineup, in both seasons, if LineStar's historical numbers were truly pre-lock (§4.1).
6. **Spreading a contest's rows across the optimizer's sequence cuts the empty weeks at no cost in expected hits**, in
   all three seasons including the holdout (§4.2). A pattern I found on the way, that the later rows beat the top rows
   at the deep lines, failed its holdout and is withdrawn (§4.3).
7. **Consistency is mostly a property of the contest, not of the lineups.** With the armed book, a satellite-heavy mix
   like Week 3's wins about one week in six; double-ups would win one week in two or three, if cash fields are no more
   than 5 points tougher than the Millionaire's, which nobody has measured yet (§5).

---

## 1. The study: do the top placers also lose?

### 1.1 Everyone, in one Millionaire

| | Week 1 ($5, 831,028 entries) | Week 2 ($20, 172,692) | Week 3 ($20, 161,682) |
|---|---:|---:|---:|
| users | 173,444 | 60,415 | 55,340 |
| users who finished the week ahead | 12.6% | 15.2% | 15.2% |
| users who cashed at least one entry | 33.7% | 27.8% | 28.5% |
| the median user's result | −100% | −100% | −100% |

### 1.2 The people at the top, in their other weeks

"Placed" is the user's best entry in one week's Millionaire. "Other weeks" are the other Millionaires that user entered.

| placed | users | other weeks played | other weeks that **lost money** | typical result in those weeks | lost in every other week played | again in the top 1% |
|---|---:|---:|---:|---:|---:|---:|
| 1st (the three $1M winners) | 3 | 6 | 67% | −51% of the stake | | |
| top 10 | 29 | 48 | **85%** | −66% | 50–100% by week | 33% |
| top 100 | 275 | 447 | **83%** | −58% | 60–87% | 32% |
| top 1,000 | 2,316 | 3,549 | 83% | −59% | 69–76% | 25% |
| top 1% of the field | 7,851 | 9,798 | 83% | −70% | 70–76% | 16% |

Across every large contest we can see (Millionaire, Play-Action, Flea Flicker, the single-entry contests, the FFWC
qualifier), users who placed in the top 0.1% of any of them lost money in 76–89% of their other weeks.

### 1.3 The heavy players

| | result |
|---|---|
| 150-entry players: weeks that were profitable | 10% / 28% / 12% (Weeks 1 / 2 / 3) |
| 150-entry players: the median week | −53% / −21% / −38% of the stake |
| A 150-entry player in the $20 Millionaire (stake $3,000), one week | median −$1,020; one week in four worse than −$1,612; one in ten better than +$960; one in a hundred better than +$31,878 |
| Players with 20+ entries in all three weeks (506) | no winning week: 62%; one: 30%; two: 7%; all three: 0.8% |
| … ahead after three weeks | 15% (median result −38%) |
| 150-entry players in all three weeks (119) | no winning week: 55%; ahead after three weeks: 18% |
| The 200 biggest spenders | no winning week: 62%; ahead after three weeks: 16% |
| Heavy players as a group, three weeks pooled | **+24%**; without their five best single weeks, **−28%** |
| Share of a heavy player's three-week winnings that came from one week | 55% (median) |

### 1.4 Where the money goes

- The top 10 users by winnings took **38%** of all Millionaire prize money over the three weeks; the top 100 took 47%;
  the top 1,000 took 63%. There were 198,279 users.
- 11.9% of users are ahead after the weeks they played.
- Users with 150 entries are 0.6% of users, hold 21% of the entries, and took 30% of the top-100 finishes and half of
  the top-10 finishes. Single-entry users are 57% of users and took 11% of the top-100 finishes.
- The 50 biggest winners over the three weeks were profitable in 49% of their weeks. Of the 37 who played all three
  weeks, 25 had exactly one winning week.

**Reading.** This is what winning at large-field tournaments looks like: most weeks lose a third to a half of the
stake, and a small number of very large weeks carry the season. It is true of the winners, of the professionals, and of
the group as a whole. A losing week is not evidence that a system is broken. A book that scores below the field's
average is (§3).

---

## 2. Is there real skill, and how large is it?

**Skill persists.** Among users with 20+ entries in two weeks, the week-to-week correlation of a user's average lineup
score is +0.12 to +0.21 (Spearman up to +0.27). The spread of true skill implied by that is about **±5 points per
lineup** (one standard deviation).

**What the best fifth achieve.** Users are ranked by their average score in the *other* weeks, and then their entries
are counted in this week:

| users' skill, measured in other weeks | entries | top 50% | cashed (top ~23%) | top 10% | top 5% | top 1% | top 0.1% |
|---|---:|---:|---:|---:|---:|---:|---:|
| bottom fifth | 31,235 | 1.03× | 1.05× | 1.05× | 1.00× | 1.03× | 1.09× |
| middle fifth | 42,617 | 1.14× | 1.27× | 1.31× | 1.38× | 1.49× | 1.95× |
| **top fifth** | 41,022 | **1.21×** | **1.39×** | **1.49×** | **1.57×** | **1.82×** | **1.97×** |

(multiples of the field's rate)

The top fifth average +0.25 standard deviations above the field, about 6–7 points per lineup. They were profitable in
**18%** of those weeks, with a median result of −41%.

**What they do differently** (traits measured in the week, skill in the other weeks; 2,542 user-weeks):

| trait | bottom fifth | top fifth | correlation with skill |
|---|---:|---:|---:|
| where their lineups rank on *our* pre-lock projection (percentile of the field) | 45th | **65th** | **+0.43** |
| ownership of their lineups (percentile of the field) | 44th | 62nd | +0.36 |
| TE salary | $4,159 | $3,947 | −0.22 |
| a second TE at FLEX | 23% | 32% | +0.20 |
| share of the portfolio on its three most-used players | 53% | 61% | +0.16 |
| QB-stack size | 1.24 | 1.35 | +0.14 |
| total RB salary | $16,458 | $16,972 | +0.14 |
| distinct players used | 81 | 76 | −0.03 |

- **They build what a projection like ours ranks highly, and they do not avoid the chalk.** That is the strongest
  pattern, and it is the opposite of the book we entered in Weeks 2 and 3.
- **Their player choices carry no detectable information beyond the crowd's.** Given our projection and the field's
  ownership, the skilled players' over- and under-weights have a partial correlation of +0.05 (t 1.1) with what players
  actually scored. The field's ownership itself is informative (+0.16, t 3.9). There is no secret list to copy.

**What our projection is worth, measured on the real fields.** Every Millionaire entry in the two clean weeks, by where
its lineup ranks on our projected sum:

| percentile of our projected sum | average score vs the field | cashed | top 10% | top 1% |
|---|---:|---:|---:|---:|
| bottom fifth | −0.35 sd | 11.7% | 4.5% | 0.2% |
| middle fifth | +0.03 | 21.8% | 9.9% | 0.9% |
| 80th–90th | +0.27 | 29.9% | 15.8% | 2.0% |
| 90th–95th | +0.30 | 30.4% | 15.8% | 2.0% |
| 95th–98th | +0.34 | 29.8% | 15.4% | 1.9% |
| 99.5th–100th | +0.33 | 30.9% | 10.5% | 0.6% |

A field lineup in the 80th–98th percentile of our projection scores about **8 points above the field's average** and
reaches the top 1% at twice the field's rate: the same level as the best fifth of heavy players. Inside that band the
least-owned fifth of lineups does worst (+0.12 sd) and the middle of the ownership range does best (+0.34 sd, top 1%
at 2.9×). In Week 2, the defect week, the top bands fell *below* the field: a projection defect turns the same method
into a handicap.

---

## 3. Where we stand on that scale

### 3.1 What we entered

| week | entries | average score vs the field | cashed | position among users with 20+ entries (Millionaire) |
|---|---:|---:|---:|---|
| 1 | 80 | **+0.09 sd** | 22.5% | 65th percentile (57 entries) |
| 2 | 97 | **−0.47 sd** | 3.1% | |
| 3 | 204 | **−0.46 sd** | 0.5% | |

In Weeks 2 and 3 the entered lineups scored about **12 points below the field's average**. The weakest fifth of heavy
players sits at the field's average. That gap, not bad luck, is what the last two weeks were.

### 3.2 What the armed Week-4 main book measures

The capped optimizer's book (36 rows, 50% exposure cap, 25% defense cap), 36 historical slates, against a
200,000-lineup field sampled from each slate's real ownership. My reproduction is identical to the lab's L18 on every
slate (means, lines and ticket counts).

| line | our rows over it | multiple of the field's rate | weeks with none | the best fifth of real heavy players |
|---|---:|---:|---:|---:|
| top 50% | 53.5% | 1.07× | 3% | 1.21× |
| top 23% (the Millionaire's cash line) | 25.8% | 1.12× | 3% | 1.39× |
| top 11% | 13.2% | 1.20× | 19% | 1.49× |
| top 5% | 6.6% | 1.33× | 44% | 1.57× |
| top 1% | 1.8% | 1.78× | 81% | 1.82× |

- **Average edge: +0.08 sd, about 2 points per lineup.** The best fifth of real players have three times that.
- **The book moves as one.** The spread of the book's weekly average is 0.57 sd (13 points). One week in four the
  whole book averages 7+ points below the field; one week in four it averages 10+ points above.
- **The deep-line multiples come from the big weeks.** In the best historical week 18 of 36 rows cleared the top-11%
  line; in 19% of weeks none did.
- So the expected change from Weeks 2–3 to Week 4 is large, about 0.5 sd (13 points per lineup), and the destination is
  a good tournament player's profile: one who loses most weeks.

**The panel may understate this season, or two clean weeks may flatter it.** In the panel's sampled field, lineups in
the 80th–98th percentile of the projection average +0.14 to +0.24 sd. In this season's real fields the same bands
average +0.27 to +0.34 (§2). In both, field lineups that merely rank high on the projection do better than the
optimizer's own book: +0.36 sd for the top half-percent of the panel's field, against +0.08 for the book. The field's
high-projection lineups are the ones the crowd also chose. The optimizer's are the ones where our projection is alone
in its optimism. §4.1 turns that observation into a test.

**The method is only as good as the projection under it.** On the 17 slates of 2022, where the replay has no market
prices and the projection is the model alone, the same book scored *below* the field: −0.17 sd, 0.95× at the cash line
and 0.85× at the top-11% line.

---

## 4. Two things that raise the level or the consistency, and one that failed

### 4.1 The crowd's ownership in the optimizer's objective

**Setup.** The armed main-book form (36 rows, 50% exposure cap, 25% defense cap). The objective is each player's
projected points plus λ × his ownership in percent (skill players only). Three ownership sources:

- **realized** Millionaire ownership: known only after lock, so it measures the ceiling;
- **our lag model's** pre-lock prediction (L05's replay sets; Spearman 0.73 with realized, players projected 3+);
- **the lab's blend** of the lag model and LineStar's projected ownership (L15's files; Spearman 0.83).

36 slates of 2023–24, rows scored against the 200,000-lineup field; multiples are of the field's rate.

| objective | average vs the field (points) | cash line | top 11% | top 5% | top 1% | weekly swing of the book (sd) | weeks with no top-11% row | weeks the whole book is below the field's average |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| as armed | +2.1 | 1.12× | 1.20× | 1.33× | 1.78× | 0.57 | 19% | 50% |
| + our lag model, λ 0.10 | +3.3 | 1.25× | 1.33× | 1.71× | 2.62× | 0.56 | 14% | 42% |
| + the blend, λ 0.10 | +5.0 | 1.26× | 1.35× | 1.40× | 2.01× | 0.53 | 19% | 36% |
| **+ the blend, λ 0.20** | **+6.1** | **1.41×** | **1.48×** | 1.53× | 2.16× | 0.51 | **8%** | **28%** |
| + realized, λ 0.05 (ceiling) | +6.3 | 1.38× | 1.59× | 1.94× | 2.55× | 0.53 | 14% | 31% |
| + realized, λ 0.10 | +8.5 | 1.54× | 1.63× | 1.84× | 1.93× | 0.44 | 8% | 19% |
| + realized, λ 0.20 | +9.5 | 1.66× | 1.84× | 1.91× | 1.93× | 0.41 | 3% | 17% |

Paired against the armed book, per slate (slate bootstrap stratified by season, 90% intervals):

| objective | average score (sd) | rows over the cash line (of 36) | rows over the top-11% line | slates better / worse | 2023 / 2024 |
|---|---|---|---|---:|---|
| + our lag model, λ 0.10 | +0.06 [−0.02, +0.14] | +1.0 [−0.1, +2.2] | +0.5 [−0.2, +1.3] | 22 / 14 | +0.09 / +0.04 |
| + the blend, λ 0.10 | +0.13 [+0.04, +0.22] | +1.1 [+0.1, +2.2] | +0.6 [−0.2, +1.5] | 23 / 13 | +0.17 / +0.09 |
| **+ the blend, λ 0.20** | **+0.19 [+0.06, +0.31]** | **+2.4 [+0.9, +3.9]** | **+1.1 [+0.1, +2.1]** | 26 / 10 | +0.24 / +0.14 |
| + realized, λ 0.10 | +0.29 [+0.19, +0.39] | | +1.7 [+0.7, +2.8] | 28 / 8 | +0.38 / +0.20 |

**The 2022 holdout** (17 slates, realized ownership only, since no pre-lock sets exist for 2022): +0.21 sd
[+0.06, +0.37] at λ 0.05, +0.22 [+0.02, +0.44] at 0.10 and +0.40 [+0.15, +0.65] at 0.20, with the weeks that have no
top-11% row falling from 41% to 35%, 12% and 6%. The ceiling replicates.

Reading:
- **It raises the level and steadies the book at the shallow and middle lines.** The book's weekly swing falls, the
  empty weeks halve, and the weeks in which the whole book sits below the field's average fall from one in two to about
  one in four.
- **It adds little at the deepest lines.** The top-1% multiple is 1.8–2.6× in every arm. Chalk does not reach the top
  1% more often, which is what the real fields show too (§2).
- **It is not L12 again.** L12 re-ranked a pool that had been built without the term, using the lag model, and read
  +1.8% (inconclusive). Here the term is inside the optimizer, so the rows are built with it, and the predictor is the
  blend.
- **The caveat that matters:** LineStar's historical projected ownership cannot be proven pre-lock. If it was refreshed
  after lock, the blend rows above are flattered. The live captures that start this week settle it.

### 4.2 Spreading a contest's rows across the sequence

A contest with N entries can take the top N rows of the capped optimizer's sequence, or N rows spread evenly over its
144 rows. Consecutive rows share a core, so they hit or miss together. All 53 slates (2022–24):

| entries | line | hits per week: top rows / spread | weeks with at least one hit: top rows / spread | weeks gained / lost | spread minus top, 2022 / 2023 / 2024 |
|---:|---|---:|---:|---:|---|
| 5 | cash line | 1.23 / 1.38 | 49% / **66%** | 13 / 4 | +0.12 / +0.17 / +0.22 |
| 5 | top 11% | 0.62 / 0.70 | 28% / **43%** | 11 / 3 | +0.18 / 0.00 / +0.28 |
| 5 | top 5% | 0.28 / 0.42 | 15% / **32%** | 10 / 1 | +0.12 / +0.06 / +0.33 |
| 20 | cash line | 5.08 / 4.72 | 81% / 91% | 7 / 2 | +0.18 / +0.11 / 0.00 |
| 20 | top 11% | 2.38 / 2.59 | 57% / 68% | 9 / 3 | +0.06 / +0.22 / +0.06 |
| 20 | top 5% | 1.26 / 1.47 | 32% / **53%** | 16 / 5 | +0.18 / +0.17 / +0.28 |
| 20 | top 1% | 0.47 / 0.38 | 9% / 15% | 6 / 3 | 0.00 / +0.06 / +0.11 |

The expected number of hits is about the same. The number of weeks with at least one is higher at every line and in
every season, including 2022, which I had not looked at when I formed the idea. With several tickets per user counted,
expected tickets are unchanged and the empty weeks fall: this is consistency at no price.

### 4.3 A pattern that failed its holdout (withdrawn)

On the 36 slates of 2023–24 the *later* rows of the sequence (109–144, after the cap has rotated the core) reached the
deep lines about twice as often as the top rows (top 5%: 1.87× against 0.99×; interval [+0.2, +8.9] points). I told the
operator about it as a pending result. On the 2022 holdout it reversed (0.49× against 1.57×), and over all 53 slates
the difference is nil (top 5%: +1.3 points, interval [−2.9, +5.2]). It is withdrawn. The armed choice, deep-line
contests taking the top average-score rows, stands on this evidence; §4.2 is the part that survived.

---

## 5. What would make results more consistent

### 5.1 What the armed book returns, by contest type

The 36-row main book, every row entered once, 36 slates, real 2026 ladders, each contest's field shifted by its
measured strength (§6). "Break-even" is the entry fee divided by the ticket's value.

| contest | the field's rate | break-even rate | as armed | with the blended ownership term | return per entry, as armed |
|---|---:|---:|---:|---:|---:|
| single-entry $5 | 24.4% | | 29.0% | 36.3% | |
| single-entry $3 | 25.2% | | 28.6% | 35.8% | |
| Millionaire, any cash | 23.1% | | 25.9% | 32.7% | |
| 20-max $3 | 22.0% | | 24.2% | 30.8% | |
| 150-max $5 (Flea Flicker) | 24.1% | | 22.9% | 28.8% | |
| 5-max $5 | 21.0% | | 18.8% | 24.2% | |
| FFWC qualifier, any prize | 5.2% | | 4.4% | 5.1% | |
| SuperSat, 2,378 entries | 1.05% | 1.25% | **1.68%** | 2.00% | **+34%** |
| SuperSat, 190 entries | 1.05% | 1.25% | **1.70%** | 1.94% | **+36%** |
| $333 wildcat satellite | 1.27% | 1.50% | **1.94%** | 2.17% | **+29%** |
| SuperSat, 594 entries | 4.2% | 5.0% | 5.1% | 5.6% | +1% |
| $20 Millionaire satellite (11 entries) | 9.1% | 10.0% | 7.5% | 8.8% | −25% |
| $4,444 satellite | 0.25% | 0.29% | 0.21% | 0.17% | −29% |

- **Above break-even:** the 2,378- and 190-entry supersats and the wildcat satellites. **About even:** the 594-entry
  supersats. **Below:** the 11-entry $20 satellites and the $4,444 satellites, whose fields score 6 to 11 points above
  the Millionaire's.
- **The FFWC qualifier is a lottery in a professional field.** $70,000 of its $76,500 pool goes to first place;
  places 71–260 get the $18 back. Three quarters of its entries come from users with 20+ entries, and its field
  scores about 6 points above the Millionaire's. At the field's own skill, one entry wins once in 5,000.
- Returns in the cash tournaments (Millionaire, Flea Flicker, single-entry) are not in the table: one first place in
  1,296 row-weeks changes the sign, so 36 slates cannot estimate them. The paid rates are the stable quantity.

### 5.2 What a week looks like, by contest mix

The same 36 slates as possible weeks; the book's rows dealt in rotation; small fields drawn 200 times each.

| mix | book | weeks ahead | weeks that lose half the stake or more | the median week | a good week (1 in 10) |
|---|---|---:|---:|---:|---:|
| **A. Week 3's mix** (satellites, qualifiers, one Millionaire seat) | as armed | 18% | 78% | −87% | +101% |
| | with the blended ownership term | 15% | 69% | −74% | +16% |
| **A2. The same without the FFWC qualifier, the 11-entry and the $4,444 satellites** | as armed | 24% | 71% | −75% | +288% |
| | with the ownership term | 25% | 58% | −67% | +173% |
| **B. Cash tournaments with flatter payouts** (single-entry, 5-max, 20-max, Flea Flicker, five Millionaire seats) | as armed | 17% | 69% | −61% | +42% |
| | with the ownership term | 14% | **42%** | **−38%** | +35% |
| **D. Double-ups** (top 45% double; field assumed 5 points tougher than the Millionaire's) | as armed | 33% | 31% | −17% | +33% |
| | with the ownership term | **42%** | 19% | −7% | +53% |

- **No tournament mix wins most weeks.** One week in four to six is what the armed book, the best real players and
  the winners themselves achieve (§1–§2).
- **The ownership term does not add winning weeks in tournaments. It makes the losing weeks smaller:** in the flatter
  contests the weeks that lose half the stake or more fall from 69% to 42%.
- **Only double-ups can win a large share of weeks,** and that row rests on an assumption nobody has measured: how
  strong cash fields are. The cash pilot's paper arms, in the chain from this week, are what measure it.

### 5.3 Recommendations, in order of evidence

Each is a nomination. The operator decides; each names its test.

| # | change | evidence | test before entry | earliest |
|---|---|---|---|---|
| 1 | **An ownership term in the capped optimizer's objective**, from the blended pre-lock predictor | §4.1: +4 points per lineup and half the empty weeks on 36 slates, both seasons; the ceiling replicates on the 2022 holdout | (a) a Week-4 paper book at T-70 with this week's live LineStar and lag captures, scored Monday; (b) one frozen lab panel on the capped form: control, blend at 0.10 and 0.20, lag at 0.10, realized as the diagnostic; (c) O1's live grading of the blend is the gate, since the historical LineStar field is unproven | paper Week 4; entry Week 5 |
| 2 | **Deal each contest's rows spread across the sequence**, not the top N consecutive rows | §4.2: fewer empty weeks at every line in all three seasons, expected hits unchanged | the rehearsal tool on Weeks 1 and 3 at the exact ladders; layout only, no solver | Week 5 (Week 4 only if rehearsed end to end by Thursday noon) |
| 3 | **Fund the contest types that measure above break-even**; treat the FFWC qualifier, the $4,444 and the 11-entry satellites as the long shots they are | §5.1, §6 | none; the operator's allocation | Week 4 |
| 4 | **Size the weekly stake for four losing weeks in five**, and judge the system on the book's score against the field, not on the week's dollars | §1–§3 | the Monday scoreboard's field comparison | Week 4 |
| 5 | **On Sunday, change only what the news requires** (inactives, their replacements, the T-70 rules) | §6: re-projection adds nothing for active players, and reshuffles a concentrated book | none; it is the smaller procedure | Week 4 |
| 6 | **Keep the cash pilot on paper every week** | §5.2 row D is the only mix that wins most weeks, and it rests on an unmeasured field | three paper weeks at or above break-even | entry no earlier than Week 7 |

**What this does not change.** The armed Week-4 configuration stands. The expected improvement over Weeks 2–3 is about
13 points per lineup, and it comes from entering a book that is no longer below the field.

---

## 6. Two side results

- **Sunday re-projection adds no information about players who play.** Between the first projection batch and the last
  one before lock (Weeks 2 and 3), the projections of active players moved by 0.26 points on average; 7% moved by a
  point or more. Accuracy is identical (mean absolute error 5.361 against 5.369; correlation with the result 0.518
  against 0.522). All of Sunday's value is knowing who is out: across every player, Week 2's error fell from 6.98 to
  5.41. So the Week-3 rehearsal in which Saturday's projections paid 24 entries and Sunday's paid 13, on the same
  lineups, is reshuffling noise in a concentrated book, not information. It argues for changing only what the news
  requires on Sunday, which is also the lower-risk procedure.
- **Field strength differs by contest, and the priority contests are the hard ones.** Points at each percentile of the
  field, minus the same week's Millionaire:

| contest | paid share | median | 90th percentile | 99th | entries from users with 20+ |
|---|---:|---:|---:|---:|---:|
| single-entry $5 (Huddle) | 24% | −2.0 | −1.3 | −2.9 | 0% |
| single-entry $3 (Pylon) | 25% | −0.8 | −0.2 | −0.9 | 0% |
| 20-max $3 (Play-Action) | 22% | 0.0 | −0.2 | +0.2 | 42% |
| SuperSat, 2,378 entries ($0.25) | 1.1% | −0.1 to +2.4 | −1.7 to +2.0 | −2.0 to +5.0 | 49–60% |
| SuperSat, 594 entries ($1) | 4.2% | +4.7 to +5.4 | +3.3 to +4.2 | −0.8 to −0.4 | 0% |
| 150-max $5 (Flea Flicker) | 24% | +3.4 | +3.1 | +2.6 | 64% |
| 5-max $5 (Nickel) | 21% | +5.0 | +4.4 | +2.3 | 0% |
| FFWC qualifier ($18) | 5.2% | +5.3 to +7.6 | +3.8 to +6.4 | +3.2 to +6.2 | 73–76% |
| $20 Millionaire satellite (11 entries) | 9.1% | +6.5 | +1.2 | | 0% |
| $333 wildcat satellite | 1.3% | +7.2 | +6.6 | | 0% |
| $555 SuperSatellite | 2.9% | +10.6 | +10.7 | | 0% |
| $4,444 satellites | 0.25% | +10.8 to +11.3 | +10.3 to +10.7 | +4.7 | 0% |

---

## 7. Limits

- **Three weeks of real fields.** Persistence, skill and the trait table rest on Weeks 1–3, and Week 2 carried our
  projection defect (it does not affect the users' own results, only the rows that use our projection).
- **We see only the contests the operator entered.** A user's other contests that week are unknown.
- **The historical panel is 36 slates of 2023–24 plus 17 of 2022**, against a sampled field, not a real one. Its
  projections are the replay's, not this season's live ones.
- **Satellite tickets are valued at face.** A ticket is an entry into another tournament.
- **The field-strength offsets** used in §5 come from one to three contests each.
- **Return on investment in top-heavy contests cannot be estimated from 36 weeks.** One first place changes the
  answer. The rates of clearing each line are the stable quantities, and they are what the tables report.
- Everything from §3.2 on is descriptive work on slates the lab has already read. Any change needs its own frozen test.

## 8. Reproduction

`reports/lab-handoffs/2026-09-29-winners-study/README.md`.
