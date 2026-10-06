# Outside review: getting to a better position on high-scoring lineups (2026-10-06)

Written 2026-10-06 (Tuesday of Week 5) by an outside reviewing agent, at the operator's request, as a response to
`reports/2026-10-06-project-status-challenges-and-attempts.md`. It answers the four open questions in that
document's §5 and adds what an outside reading of the code, the ledgers and the published literature suggests.
Nothing here is a verdict: every suggestion is a candidate for the in-season adoption track
(`reports/2026-09-19-in-season-adoption-track.md`) and names its mechanism, the exact change, the evidence, the
earliest usable week, how it is tested, and the nearest thing already tried. Public repository: no dollar amounts
of stakes, no user names.

**Corrected 2026-10-06 (evening)** after the reviewing agent's read: §0 item 4 and table rows 2 and 10, §1(b), §1(d),
§2.2, §2.4, §3.4, §4.1, §4.2, §4.3, §4.5, §7 and Appendix B. The first version said the simulator judged studies 24–37;
it did not. Those studies score every book row and every sampled-field row on the realized points of 36 past weeks
(`s24_qb_game_cap.py:305-309`); only the opponents' rosters are sampled. The corrections are marked in place.

What was read: the status document; the study list and both proposal files of 10-04; the Week-4 post-mortem, the
money-gate result and the Week-5 decision sheet; the winners' spread, props-and-winners, regulars' choices and
stacking reports; Addenda 121–142; `HANDOFF.md` from 09-28; the lab `LEDGER.md`; the briefing of 09-14 (§3, §7);
and the live code: the pinned lab clone at `f69598b` (`live_week.py`, `pipeline.py`, `core/simulate.py`,
`core/game_sim.py`), `scripts/union_reselect.py`, `scripts/field_sampler.py`, `enter_layout.py`, the props job
and the four weekly-record scripts.

---

## 0. Summary

1. **The deficit is everywhere and grows toward the tail.** Over Weeks 1–4 the entered rows' pooled median finish is
   p59.7, and their share of the top 20 / 10 / 5 / 1% is 0.55 / 0.39 / 0.15 / 0.18× chance (HANDOFF 10-05 18:18).
   The book's score distribution is both lower and narrower than the field's. A $500-plus Millionaire finish is roughly the top 0.25%;
   that is where the gap is widest.
2. **Selection has no skill, so the pool's density of winning rows is the quantity that matters.** With the entered
   book at the 52nd percentile of random books from the same pool, P(at least one big win) is, to first order,
   `1 − (1 − d)^26` where `d` is the share of pool rows that would cross the line. Every lever should be judged by
   whether it raises `d` on the real field, and `d` can be measured every week with thousands of rows.
3. **The two changes that moved real weeks were inputs, not construction**: the ownership term (+4.1 points per
   lineup in the Week-4 replay) and FP's projections (the Week-4 replay held). More than a dozen construction studies in the
   simulator read "no difference". That pattern is itself the finding: the information goes in through the means.
4. **The construction verdicts were scored on real results, not on the simulator** (corrected 10-06). Studies
   24–37 score every book row and every sampled-field row on the realized points of 36 past weeks; only the
   opponents' rosters are sampled. Their limits are the ones the status document names: 36 weeks, our older
   projections, and a sampled field whose rosters are less stacked than real fields and carry no duplicates. The
   simulator's dependence (independent touchdowns, weak cross-team factors, a constant DST) matters where worlds
   build rows: the boom pool, the tail sleeve and the replacement step. The live-week paper co-run (study 38) is
   the court for the projection question, and this review proposes giving it more arms, as information (§2).
5. **The Week-5 book is a concentration machine by construction**: 26 sequential mean MILPs on FP mean plus
   0.20 × projected ownership, with up to 7 of 9 players shared between rows. Ten players at the 13-row cap is what
   that objective produces. The fix is not another cap; it is to change what the rows are optimizing for, and to
   measure it on the real field.

Ranked recommendations (details in the sections named):

| # | Suggestion | Class | Earliest | Section |
|---|---|---|---|---|
| 1 | Pool hit density on the real field as the headline weekly metric; a Sunday paper-arm ladder scored Monday | eval | W5 (paper) | §2.1–2.2 |
| 2 | Dependence audit of the simulator's worlds against nflverse, for the pool, tail sleeve and replacement step that build from them | audit | W6 | §2.4 |
| 3 | Fit the ownership term on W1–4 against a market-quality base; keep its information role, drop its leverage role. Done 10-06: adds nothing beyond the projection; both agents recommend 0 (decision sheet row 13) | C | W5 (operator) | §3.2 |
| 4 | Aggregate projections (FP + props-implied + a consensus leg); the existing accuracy script is the test | R/C | W6 paper, W7 | §3.1 |
| 5 | A props snapshot after the 10:30 CT inactives; use it at T−70 | R | W5 if cheap, else W6 | §3.3 |
| 6 | A finish model trained on the real Millionaire fields, used as selector and generator tilt (study 10 re-aimed) | S | W6 paper | §4.2 |
| 7 | Game-environment coverage: allocate the 26 QB slots by P(top game), not by a cap | S | W6 paper | §4.3 |
| 8 | Dupe-aware generation and dealing (salary-left randomization, ownership-product penalty, low-dupe rows to one-seat satellites) | E | W6 | §4.4 |
| 9 | Contest allocation by P(big win) per dollar and shark share; drop the two classes where regulars hold 28–54% of entries | E (operator) | W5 plan | §5 |
| 10 | Withdrawn 10-06: the harness's across-contest combination is exact given each week's real result | — | — | §4.5 |

---

## 1. What the evidence says the bottleneck is

Facts, with where they are recorded:

- Median finish p59.7; share of top 1 / 5 / 10 / 20% = 0.18 / 0.15 / 0.39 / 0.55× chance (HANDOFF 2026-10-05 18:18).
- Our picks −3.8 points per lineup vs the rest of the Millionaire; the 117 regulars +6.1 (p 0.002). Their skill is in
  the early games before kickoff (+10.2 vs a null of −0.8, p 0.009); in the late games +14.1 vs a null of +11.1
  (p 0.12). So the edge is information at lock, not late swap (`reports/2026-10-05-regulars-player-choices.md`).
- Week 4: none of the Millionaire top 100 was in the pool; the best pool row (211.8) would have finished about
  100th (209.2). Four correlated busts; ownership sum 152 vs the field's 110; a third of our rows duplicated in the
  field (`briefings/2026-week-04/2026-10-05-week4-post-mortem.md`).
- Top 1% / field / ours: QB+2 44 / 30 / 94%; bring-back 59 / 43 / 97%; dual stack 46 / 46 / 15%; games per lineup
  4.9 / 5.3 / 4.1 (`reports/2026-10-05-stacking-and-rb-research.md`). Our book is the rigid outlier in both
  directions: always the same stack, fewest games.
- On players with prop lines, props alone beat everything (MAE 5.31 vs served 5.50 vs model 5.88); the optimal
  model weight is 0% in every leave-one-week-out fold; the model is biased −1.7 (`reports/2026-10-06-props-and-winners.md`).
- The top-total game is the slate's top-scoring game only 16–19% of the time (study list item 5); the field
  under-owns the top total (leverage 1.31, X1).
- P(top-N) selection against the modelled field lost to expected-max (PREREG-098: −0.030 [−0.048, −0.015], 9 wins
  / 44 losses). The briefing's structural conclusion: "points is the wrong axis"; the points-optimal book sits
  36–49 points below the winner and reaches the winner about once in 35 weeks; no ledger lever moves the book by
  more than ~2 points.
- Lab cohort 004 (a two-regime game-environment overlay in the simulator) raised ≥210-point weeks from 4.2 to
  7.2 in every seed and was never adopted (`nfl2/LEDGER.md` rows 004, 004×4).

The diagnosis these facts support:

**(a) The winning rows exist in the pool at low density, and the selector cannot find them.** The pool reaches
the top-100 line about once per 4,800 rows; the book draws 26 of them at chance. Raising `d` (more winning rows
per thousand) and raising selection skill above chance are the only two routes to the operator's event. Everything
in §3 targets `d`; §4.2 targets selection skill with a method that does not rely on the simulator.

**(b) The construction verdicts stand on real results; the simulator's dependence matters where rows are built**
(corrected 10-06; the first version said the simulator judged these studies). Studies 24–37 score the book's rows
and the sampled field's rows on each past week's realized points (`s24_qb_game_cap.py:305-309`), so real
touchdowns and real correlations are in every verdict. What is simulated is the opponents' rosters: sampled per
slot with a 70% one-slot stack propensity (`field_sampler.py:28,47–50`), no bring-backs or game stacks, no
duplicates, ties as losses. Real fields carry 43% bring-backs and 46% dual stacks, so the sampled field's top
tail is, if anything, easier to cross when a game goes off; that does not bias the verdicts against spreading.
The simulator's own dependence is a separate matter: in the pinned `core/simulate.py`, `rec_tds` and `pass_tds`
are independent Poissons on fixed means with `TD_LEDGER` off (lines 418–429); cross-team volume factors correlate
0.1–0.2 by design (`game_sim.py:300–308`); DST is a constant (`live_week.py:205`). Those worlds build the boom
pool, the tail sleeve and the replacement rows, which is where §2.4's audit applies. A linked-touchdown version
was tested and buried on the panel: Addendum 89 (2026-08-05), TDLEDGER2 19 vs the control's 27 weeks, "hand-specified
TD event coupling reduces tails even when mean-preserving and correctly grouped"; `TD_LEDGER` stays off by that
verdict.

**(c) The Week-5 objective concentrates by design.** `mix_rows` solves 26 MILPs on FP mean + 0.20 × projected
ownership (`union_reselect.py:303`), each allowed to share 7 of 9 players with every earlier row. For a 30%-owned
player the term is +6 points on a 15–20 point projection; the ten best-value players recur until the 13-row cap
stops them. The regulars' spread (about 2 players over 40%, 53 distinct non-QB players, 11 QBs at our book size)
is not a cap; it is a different objective, one that pays 2.4–3.2 projected points for a new game where we pay 0.7.

**(d) The cost of spreading is real and was measured on real results** (corrected 10-06). Under our older
projections, the capped books' replacement rows scored 2.4–4.3 points lower in mean finish over 36 real weeks,
and no gain on P(≥1 big seat) appeared. That answer stands for those projections. Better projections make the
projected gap more real, not less, so the open question is not whether the harness was fair but whether the
benefit (holding the game that goes off, fewer correlated busts) outweighs the cost under FP projections and the
operator's utility. That is study 38's question, and §4's ideas are arms for it.

---

## 2. Evaluation that can read in four weeks (§5 question 2)

The binary event (at least one big win) has a weekly probability in the low single digits; detecting a doubling
needs on the order of a hundred weeks. The proxies below are monotone in that event and have far more
observations per week. Adopt on the proxies under the "no measured cost" rule; confirm on the event over the
season.

### 2.1 Pool hit density on the real field (headline metric)

- **What:** for a pool or book built from pre-lock inputs only, the share of rows at or above each contest's
  big-win line in the real settled field: the Millionaire $500 line (about the top 0.25%; a published structure
  pays $500 to places 301–400), and each satellite class's seat line. Report `d` per line and the implied
  `P(≥1 | 26 at chance) = 1 − (1 − d)^26`, plus the exact monkey version (the existing M2 draw already scores
  random books in the real field; add the per-line share as an output).
- **Why it has power:** thousands of rows per week instead of one event. Rows are correlated, so quote a
  cluster bootstrap over the QB-game, not a plain binomial interval.
- **Paired arms:** two pools or books built from the same T−70 inputs differ only in the lever; the weekly
  difference in `d` is paired, and four weeks of paired differences are readable when the lever is real.
- **Existing pieces:** `scripts/moneygate_monkeys.py` (M1/M2/M3 in the real fields), `moneygate_score.py`
  (settlement and tie splitting). The addition is the per-line share and a receipt that names the pre-lock inputs.
- **Caveat:** since the FP switch, the pool (centred on our projections) and the book (FP means) use different
  projection sources; M1/M2 now benchmark the book against a pool built on different information. Build the
  monkeys' pool on the same source as the book, or state the confound in the Monday line.

### 2.2 A Sunday paper-arm ladder, scored Monday (study 38, generalized)

- **What:** every Sunday at T−70, build K paper books from the same inputs, each one setting away from the armed
  book, by the same `union_reselect.py` machinery (each is 26 MILPs, minutes of CPU). Never entered. Score Monday
  in the real fields on: best-of-26 finish percentile; rows above each big-win line (the operator's utility);
  mean finish percentile (the guard); exact duplicates found in the field; ownership sum; games and QBs covered.
- **Arms worth a slot now** (each is one setting): ownership term 0 / fitted (§3.2) / 0.20; shared-player limit
  7 / 5; QB cap 5 vs coverage allocation (§4.3); salary-left randomization on/off (§4.4); the regulars' structure
  (study 38 as frozen); the finish-model selector (§4.2) once it exists.
- **Rules that keep it honest:** arms are frozen before each lock; an arm added mid-season is graded from its
  first prospective week only; nothing is tuned on a week already scored; the record is a committed file.
- **Decision rule** (corrected 10-06): four weeks are four outcomes, however many rows are scored in each; a
  "3 of 4" rule passes by luck about 1 time in 3 for one arm, and with several arms one will pass by chance. So:
  one pre-specified primary arm per question under study 38's rule (ahead in 4 of 4, guard intact); every other
  arm is information, reported as paired weekly differences in `d` and in rows-above-line with their within-week
  intervals, never adopted on its own record. Within-week pairing removes the slate's common shock and makes each
  week's difference precise; it does not add weeks.
- **Cost:** K extra 26-row solves at T−70 on the laptop; well inside the hardware rule.

### 2.3 Player-level accuracy in the tail, ownership-weighted

`weekly_projection_accuracy.py` reports MAE, bias and Spearman. For a max-of-26 objective, add: the pinball loss at
τ = 0.9, the top-decile hit rate (did the source's top-decile players land in the realized top decile), and the
same metrics weighted by FP ownership (errors on the players the field and we actually roster are the ones that
cost). These have ~300 observations per week and will separate projection sources within 3–4 weeks where MAE will
not.

### 2.4 A dependence audit of the simulator's worlds (where worlds build rows)

Scope, corrected 10-06: the worlds build the boom pool, the tail sleeve and the vetting replacement rows; they do
not judge studies 24–37. Run once, outcome-blind to any lever, on nflverse history and the four real 2026 fields:

- Pairwise DK-point correlations in the simulator's worlds vs the empirical ones: QB–WR1, QB–WR2, QB–TE, QB–RB1,
  QB–opposing WR1, WR1–opposing WR1, team-level sums, DST–opposing QB. Public figures put QB–WR1 near 0.46; the sim
  with the ledger off will be lower by construction. Run the same table with `TD_LEDGER=1` and in the `hsim`
  bank: whichever bank is closest to the empirical table is the one the boom pool, the tail sleeve and the
  replacement step should draw from.
- The sampled field vs the real field: stack-type shares (QB+1 / QB+2 / bring-back / dual), games per lineup,
  ownership sum distribution, exact-duplicate counts, salary-left distribution, and the composition of the real
  top 100 by those features. The cutoff correlation of 0.987 says the field's score quantiles track; it does not
  say the top 100 look right.
- Marginal calibration by position in the tail (P5 is open: TE 17.5% above its p90 vs a nominal 10%), with
  ties-at-zero handled.

The linked-touchdown version was buried by Addendum 89 (19 vs 27 weeks on the panel). The audit is still worth
a day: if that version matched empirical dependence better and still built worse books, the pool's problem is not
dependence, which narrows the search.

---

## 3. Better pre-lock information (§5 question 1)

### 3.1 Aggregate, do not pick (class R/C)

- **Mechanism:** the 12-season, 11-source study (FantasyFootballAnalytics, 2014–2025) found the aggregate beat
  every standalone source in 69% of comparisons, and that single-source rankings are unstable year to year. FP is
  one source. The props-implied projection is a second, and it is the best one you have on the players it covers.
- **Exact change:** add a consensus leg (FantasyPros' weekly consensus is itself an aggregate of ~100 analysts and
  is cheap; a second independent paid source would do), and serve the selection mean as a fixed-weight average of
  FP, props-implied and the consensus, with our model at weight 0 until the O-22 retrain earns weight in the
  weekly check. Track B2 already tests a 1/3-1/3-1/3 of model, market and FP; replace the model third with the
  consensus third, because the props report found the model's optimal weight is 0 in every fold.
- **Test:** `weekly_projection_accuracy.py` with the extra columns and §2.3's tail metrics; adoption when the
  aggregate beats FP alone on top-decile hit rate in 3 of 4 weeks. Earliest W6 on paper, W7 in the book.
- **Nearest prior:** ETR was proposed as a purchase (08-09, 09-03) and not bought; a multi-source consensus was
  never proposed; a heavier *uniform* market weight was closed (L04), which is a different question from a
  three-leg aggregate.

### 3.2 Ownership is information; size it as information (class C)

- **Mechanism:** the term helped on real weeks (+4.1 per lineup in the Week-4 replay) and in the simulator, which
  cannot see information. On real weeks the likely reason is that the field's ownership encodes news and sharper
  projections our model lacked. Under FP as the base, that information may already be in the mean; the props
  report found the regulars lean toward props-liked players "but not beyond FP". Top-heavy theory (Haugh & Singal)
  says the leverage role of ownership should be zero to negative, not +0.20.
- **Exact change:** on W1–4, fit realized DK points on FP projection, FP projected ownership and salary, by
  position, leave-one-week-out. Set the tilt to the fitted ownership coefficient in points per ownership point
  (expect something far below 0.20 if FP already carries the news; keep 0.20 only if the data say so). This is a
  Wednesday read; it is one env value in the build.
- **Test:** the fitted coefficient is the test; the paper ladder (§2.2) carries 0 / fitted / 0.20 as arms.
- **Done 2026-10-06 by the reviewer and the laptop** (decision sheet row 13; arming checklist item 7). FP's
  projections exist only for Week 4, so the fit used market and served projections over Weeks 1–4: beyond a
  market-quality projection, popularity adds nothing, and FP's is a market-quality projection. On Week 4's real
  slate the Week-5 book reads a 0.9% chance of a big win with the term and 3.4% without (one week, the week the
  chalk busted; production's replay reproduces the lab, 0.0094 vs 0.0336). In Week 4, 47% of the Millionaire
  entries had exact copies in the field. Both agents recommend 0 for Week 5; study 38 tracks both settings live;
  the setting is reversible each week. The operator decides.
- **Nearest prior:** studies 29 and 31 tuned the term on real results under our projections, where it carried
  information the model lacked. Study 22a (residual calibration) is the home for the standing weekly fit.

### 3.3 Sunday morning: capture the market after the inactives (class R)

- **Mechanism:** the regulars' edge is in the early games, i.e. in what is knowable between the 10:30 CT inactives
  and the 12:00 lock. The props job's last snapshot is the Sunday early pull at 04:30 CT; the T−70 build uses "the
  latest pre-lock snapshot", which is six hours stale on the inactives. Prop lines are pulled or repriced within
  minutes of an inactive list; the move is the fastest public reaction to a backfield or receiver change.
- **Exact change:** one more props pull at about 10:45 CT on the existing job (a scheduler on an existing Cloud
  Run job needs no new job); make the T−70 build prefer it. Today props reach the money path only through the
  production blend that centres the simulations and the weekly FP + props check, so the payoff arrives when §3.1
  puts a props leg in the selection mean; the capture should exist before then. Fix O-4 (moved lines kept as duplicate rows) first or
  the new snapshot double-counts. Confirm FP's T−70 capture is the post-inactives one (it is "the newest before the
  build"; log its timestamp in the receipt).
- **Test:** props-implied accuracy at the 10:45 snapshot vs 04:30 on early-game players, weekly; and study 12's
  "where the points went" (beneficiaries of an inactive) becomes a check that the beneficiaries' lines moved.
- **Nearest prior:** line movement from Thursday to lock was null (Add. 17, "closes absorb the news"); that is a
  different window from the 90 minutes after inactives.

### 3.4 The generator's distributions: the parts of the simulator that still touch money

The Week-5 main book is a mean MILP and does not use the simulator, but the boom pool (the corpus and the monkey
benchmark), the tail sleeve, the vetting replacement step and every study do. Three cheap inputs:

- Touchdown coupling: the ledger exists (`TD_LEDGER=1`); the linked version was buried by Addendum 89
  (19 vs 27 weeks on the panel). §2.4 can still say whether it was closer to empirical dependence, which matters
  for interpreting that verdict, not for reopening it.
- DST variance: a constant DST never produces the 2–5× salary defensive score that top-100 lineups carry.
- The two-regime game-environment overlay (lab 004) doubled ≥210-point weeks in every seed and sits unadopted;
  as a *generator tilt* (more boom worlds from the shootout regime) it changes the pool's `d` without changing the
  judge, which is the clean way to use it.

### 3.5 Not worth re-chasing here

Line movement Thursday-to-lock (null), alternate-line ceiling bumps (null), LLMs as forecasters (ruled out),
prediction markets (killed), same-game parlay correlations (no provider). Public DFS content repeats these ideas;
the ledger already paid for them.

---

## 4. Construction for "at least one big win" without paying for it (§5 question 3)

### 4.1 What the historical verdicts settle and what they leave open (corrected 10-06)

On real results over 36 past weeks under our older projections, caps cost 2.4–4.3 points of mean finish and
brought no gain on P(≥1 big seat); the winners' mix, the QB cap and the regulars' structure read no difference.
Those answers stand for those projections. Two things are open: the same questions under FP projections (study
38), and whether an objective other than a cap, one that makes 26 rows each good *and* jointly diverse, does
better than the mean-plus-term MILP. The three ideas below are arms for study 38's court, offered as information;
none is a claim that the harness was wrong.

### 4.2 A finish model trained on the real Millionaire fields (study 10, re-aimed) (class S)

- **Mechanism:** PREREG-098 asked the simulator to rank rows by P(top-N) and lost; the simulator's world model has
  no skill in the joint tail. A model fitted to the *real* top finishers inherits the field's information
  (through ownership and FP) and the real dependence (through stack and game features), and asks nothing of the
  simulator.
- **Data:** each 2026 week's full Millionaire standings (W1–3 in BigQuery, W4 local) give about 160,000 rosters
  with finish; positives are rows at or above the $500 line (about 400 per week), negatives a random 20,000.
  Features are pre-lock and lineup-level: sum of FP projection; sum and log-product of FP ownership; salary left;
  games and teams; stack type (QB+1 / QB+2 / QB+3, bring-back, dual stack); the QB's team total and game total;
  count of players in the top-total game; sub-$4k players; DST salary and ownership; a 7+-point favourite RB flag.
  Fifteen features, L2 logistic (or a shallow monotone GBM), walk-forward only (W1–3 → W4, W1–4 → W5 on paper).
- **Operational test, the one that matters:** score our pool rows with the model, take the top 26 under the
  book's caps, and read the Monday monkeys: if the model-picked book sits above the 80th percentile of random
  books in 3 of 4 weeks, there is selection skill where every ranking rule so far had none (study 32). The
  held-out AUC is secondary.
- **Uses:** (i) as the selector, replacing the mean-plus-term objective (the logistic score is additive in the
  player terms and linear in a handful of lineup terms, so it fits the MILP; the product term is a log-sum);
  (ii) as a generator tilt in the boom family.
- **Risks and controls:** four weeks of positives; it will partly learn "what the field liked" and, as the
  reviewing agent notes, the shapes that happened to win. Team and game identities are excluded from the features
  so it cannot learn which games went off by name, but that is a mitigation, not a cure. Keep the feature set
  small and structural, regularize hard, never refit on a scored week, grade only prospectively, and treat it as a
  Week-7-or-later item that earns a slot as weeks accrue (eight by Week 8). Unifies study 10 (1.49M contest lineups), X1 (scenario
  arbitrage), X5 (pattern mining with an FDR guard) and P8 (duplication-aware EV) into one fitted object.

### 4.3 Cover game environments; stop predicting the one that goes off (class S)

- **Mechanism:** the winner's game was stacked and brought back in 6 of 8 sampled Millionaire weeks; the top-total
  game is the top-scoring game only 16–19% of the time; Week 4's deciding game was in 31–35% of pool rows and 0 of
  26 book rows. The event the operator wants is "one of my rows was in the game that went off, built as a game
  stack". With 26 rows and ~13 games that is a coverage problem, not a prediction problem.
- **Exact change:** fit P(game g is the slate's top DK-point game | total, spread, pace proxies) on 2019–2025
  nflverse with pre-game lines (point-in-time safe; hundreds of slates). Allocate the 26 QB slots in proportion to
  that probability with a floor of one row for every game above a small threshold; those rows take the A1 shape
  (QB+2 plus bring-back) in their game. Expect 9–11 QBs, which is what the regulars run, derived rather than
  copied. The remaining shapes (A2, B, C) fill from the same allocation.
- **Cost under our ratings:** about 2–3 projected points on the non-top rows, i.e. inside the noise of §1(d).
- **Test:** a §2.2 arm; the direct read is "rows above the line" and "did the book hold the top game", which is
  binary per week but has a strong prior (6 of 8).
- **Nearest prior:** study 24 (a cap on the top-total game's QB share, −22% seats) and study 37's extra-QB arm,
  which read even under our ratings. This is 37's sibling with the allocation derived from a fitted probability
  rather than copied; it belongs beside study 38 as one more arm, not as a separate program.

### 4.4 Duplication-aware generation and dealing (class E)

- **Mechanism:** a third of Week-4 rows, and 47% of the Millionaire entries, had exact copies in the field
  (post-mortem; decision sheet row 13); a 0.20 term at ownership sum 152 makes that worse. Ownership *product* predicts duplicates (r² 0.56) far better than ownership sum (r² 0.24);
  rows using more than $49,500 of salary average 23.7 duplicates vs 4.9 at or under (ETR). A $500 tie splits
  harmlessly; a one-seat satellite tie is a coin flip for the seat.
- **Exact changes:** (i) draw each row's salary target from a band (e.g. 48,800–50,000) instead of the fixed
  $49k floor (O-15 notes the floor does not reach the lab build; this needs the same plumbing); (ii) compute each
  row's expected copies as `N_field × Π ownership_i × c` with `c` fitted on the four real fields; (iii) in the
  layout, send the lowest-copy rows to the one-seat satellites and tolerate copies in the Millionaire.
- **Test:** copies are directly observable Monday (exact matches in the standings), so this reads in one week
  per arm. Earliest W6.
- **Nearest prior:** Add. 18 found dupe risk ≈ 0 for the then-book (pre-term); the 09-29 review said ignore
  duplication; study 24's all-distinct deal was no difference. The term changed the book; the Week-4 count changed
  the fact.

### 4.5 Distinct rows per entry, and a check on the harness (class E)

**Withdrawn 2026-10-06.** The reviewing agent is right: the harness scores each week on its real result, so a
reused row's events across contests are independent given that result (each contest's field is its own draw), and
the risk of reusing a row shows up across the 36 weeks as it should. The Poisson-binomial is exact. Study 24's
"no difference" for the all-distinct deal stands as measured; whether to deal distinct rows anyway is the
operator's preference, not a harness defect.

### 4.6 Late swap: standings-aware, paper only, later

The satellite late swap on the armed book read neutral (412 → 400 tickets, leaning against); forcing late players
was harmful (L22); the lab's recourse prototype was invalid because it used final early-game scores. The version
the public literature describes (tier live rows after the early window; dead rows chase ceiling and low ownership
in the late games, live rows protect) was never built (R11). Since the regulars' edge is early-game information,
this is second-order; build it as a paper arm with timestamped in-game state only after §3 and §4.2–4.4 have
their first reads.

### 4.7 The knobs that exist today

For the paper ladder, each of these is one setting in the current machinery: the shared-player limit (7 → 5 or 6),
`MAX_PER_GAME`, the per-row allowance to pay projected points for a new game (the regulars' −2.4 to −3.2), the QB
cap vs §4.3's allocation, the term (§3.2), the salary band (§4.4), the shape weights. None should enter the book
from the simulator's verdict alone.

---

## 5. Contests and staking under a lottery utility (§5 question 4)

The operator's utility is "at least one of {a $333, $555 or $4,444 qualifier seat, a $500-plus Millionaire finish}
per week". Under that utility, for small per-entry probabilities, `P(≥1) ≈ Σ p_i` over entries, so the budget goes
where `p_i / fee_i` is highest, one entry per contest, distinct rows.

- **Compute `p_i / fee_i` per contest class from the private table.** `p = (seats / entries) × R_class`, where
  `R_class` is our relative rate at that class's seat line (the table already has our share at the top 1 / 5 / 10 /
  20% pooled; compute it per class). This is a spreadsheet from data on hand, not a study.
- **Shark share by class is already measured:** regulars hold 1.2% of Millionaire-satellite entries, 10.7% of
  $555, 12.7% of $333, 27.8% of $4,444 and 53.8% of FFWC entries (HANDOFF 10-05). The Millionaire itself is about
  11% regulars (117 × 150 of ~160,000). Unless `R_class` says otherwise, the $4,444 and FFWC classes are where our
  relative rate should be lowest; the $333 / $555 qualifiers and the Millionaire's $500 line are where the same
  dollars buy the most `p`.
- **Overlay is a free increase in `p`:** an unfilled contest has fewer entries per seat. The overlay back-test found
  overlays only in Showdown copies (1.10–1.36). The Showdown builder exists and is not deployed; the $4,444 Showdown
  satellite is 28% regulars. A medium-term option, after the main-slate work, with the shark caveat.
- **Independent slates raise `P(≥1)` at the same total** because events on one slate are positively correlated and
  events across Thursday, Sunday main, Sunday night and Monday are not. Second-order; worth one line in the plan.
- **Ties:** in one-seat satellites a duplicate at the seat is a coin flip; §4.4(iii) is the operational answer.

---

## 6. A four-week program, in order

**This week (Week 5; nothing enters the money path).**
1. §2.4 audit of the simulator's dependence and of the sampled field against the four real fields. One day.
2. §3.2 regression of realized points on FP projection and FP ownership, W1–4. Half a day. Put the coefficient
   to the operator with the Week-5 Friday decisions; Week 6 unless he wants it now.
3. §3.3: the 10:45 CT props pull if it fits the Saturday arming without touching the rehearsed path; otherwise W6.
4. §2.1–2.2: arm the paper ladder beside study 38 for Sunday (term 0 / fitted / 0.20; shared-player 5; salary
   band; all-distinct), scored Monday with `d` per line. The arms are frozen Saturday.

**Week 6.**
5. §3.1 consensus leg in the accuracy script (paper); §2.3 tail metrics.
6. §4.2 finish model v0 trained on W1–5, scoring the W6 pool on paper; the monkeys read on Monday.
7. §4.3 P(top game) fit on history (point-in-time), the QB allocation as a ladder arm.
8. §5 contest allocation by `p / fee` for the Week-6 plan (operator).

**Weeks 7–8.**
9. Adopt, by the ladder's rule and the operator's say, whichever arms are ahead on rows-above-line in 3 of 4 weeks
   with the guard intact. The adoption track's "preference with no measured cost" class covers an arm that is
   level on the guard and ahead on the event proxy.
10. Keep the frozen six-season readers for scientific verdicts, separately, as the policy already says.

---

## 7. What to stop doing

- Treating the historical "no difference" verdicts as settled under FP projections (corrected 10-06: they were
  scored on real results and stand under our older projections; the transfer to FP is study 38's question).
- Tuning the ownership term, or any lever, inside the simulator. Size it on real weeks (§3.2).
- Ranking objectives inside the simulator (p90, quantiles, P(top-N), coverage ladders). The ledger closed them
  five times; with selection at chance they will keep closing. §4.2 is the only ranking idea in this document, and
  it is trained on the real field.
- Adding construction studies before the information work has its first weekly reads. More than a dozen studies
  produced one preference; two input changes moved real weeks.

---

## Appendix A. Outside sources used

- Haugh, M. and Singal, R., "How to Play Fantasy Sports Strategically (and Win)", *Management Science* (2021).
  Top-heavy objective as a function of your score minus the top order statistic of the field; high own variance and
  negative covariance with the field's best lineup; a Dirichlet-multinomial opponent model from ownership and
  salary; the objective is monotone submodular across entries; 2017 NFL season, 350% vs 50% for the benchmark that
  ignored opponents.
- Hunter, D. S., Vielma, J. P. and Zaman, T., "Picking Winners in Daily Fantasy Sports Using Integer Programming",
  arXiv 1604.01455. P(at least one entry wins) is submodular; build entries greedily, each maximizing expected
  score subject to a lower bound on variance (stacking) and an upper bound on overlap with earlier entries.
- Mlčoch, D. et al., "Competing in daily fantasy sports using generative models", *International Transactions in
  Operational Research* (2024). A mixed-integer quadratic program over mean, variance and covariance for top-heavy
  payouts.
- FantasyFootballAnalytics, "We analyzed 12 seasons of fantasy football projections" (2026): 11 sources,
  2014–2025; the aggregate beat each standalone source in 69% of comparisons; single-source ranks unstable;
  projections explain 14–26% of variance.
- Establish The Run, showdown duplication study: ownership product r² 0.56 vs cumulative ownership r² 0.24 for
  duplicates; 23.7 vs 4.9 duplicates above / at or under $49,500.
- RotoStreetJournal, Millionaire Maker winners 2020–2022: the winner stacked and brought back the week's
  highest-scoring game in 6 of 8 weeks; 87.5% of winners brought back an opponent.
- 4for4 / ETR winning-lineup reviews (2022): top-100 lineups QB+2WR 19% vs field 13%; triple stacks 7.7% vs 4.3%.
- Stokastic, "NFL DFS Late Swap": tiering of live rows after the early window; the field largely does not swap
  (claim, no data).
- Published Millionaire Maker payout structure: places 301–400 pay $500; a Masters Millionaire had 205,732 entries
  and 149,657 unique rosters, the most-used entered 162 times.
- 4for4 correlation tool: QB to his WR1 about 0.46.

## Appendix B. Where each suggestion sits against the ledger

| Suggestion | Nearest prior attempt | Its status | What is different here |
|---|---|---|---|
| Pool density metric (§2.1) | Monkeys M1/M2; pool oracle (lab) | In use | Per-line share as the headline; paired arms; cluster bootstrap |
| Paper ladder (§2.2) | Study 38; X3 bandit | 38 frozen; X3 proposed | K arms, continuous paired metrics, one record file |
| Sim dependence audit (§2.4) | P6 "correlation repair" (closed); Addendum 89 (linked TDs buried, 19 vs 27); field calibration script | Closed | A calibration check of the worlds that build rows; not a reason to doubt the real-results verdicts |
| Aggregate projections (§3.1) | B2 1/3 blend; L04 uniform market weight (closed); ETR purchase (not bought) | Pending / closed | Three independent legs incl. a consensus; model at 0 |
| Fitted ownership term (§3.2) | Studies 29, 31; 22a | Done 10-06: 0 recommended (decision sheet row 13) | Sized on real weeks against a market-quality base |
| Post-inactives props (§3.3) | Add. 17 line movement (null) | Closed | Different window: the 90 minutes after inactives |
| Finish model on real fields (§4.2) | PREREG-098 P(top-N); study 10; X1; X5; P8 | 098 lost; others proposed | Trained on real finishes, not simulated ones |
| Game coverage (§4.3) | Studies 24, 37, 1; lab 004 | No difference / unadopted | Allocation from a fitted P(top game), not a cap or a copy |
| Dupe-aware (§4.4) | Add. 18; study 24; P8/R12 | Ignored / scope later | Measured on W4; cheap; reads in one week |
| Distinct rows (§4.5) | Study 24 all-distinct | No difference | Withdrawn 10-06; the combination is exact |
| Contest allocation (§5) | P1; study 21; X2 | No edge anywhere / proposed | Lottery utility, `p / fee` by class from data on hand |
| Late swap (§4.6) | L11, L22, lab 009, R11 | Neutral / harmful / invalid / never built | Paper, later, with timestamped state |

---

## 8. Added 2026-10-06 (15:40 CT): what can be tried THIS week, after the afternoon's HANDOFF entries and the graph

Read: HANDOFF 11:28–15:10 (tilt 0 armed; study 37 read; study 38 frozen at `c979dddd` with RBC0 as an exploratory arm;
the Neo4j load and the reviewer's mining). The graph says the regulars' edge at our size is *RB-led concentration
where projections are reliable, breadth where they are not*: 5.2 heavy players (48% RBs) and 6.5 QBs at 26 rows vs our
12 heavy and 5 QBs; their exposure tracks the field's ownership (ρ .93–.96, so they are not contrarian); their WR/TE
overweights beat projection, their RB overweights do not; within a regular's week his top-1% rows do not differ in
structure from his others. In order of what can reach Sunday under the money-path rules:

1. **Make the FP freshness gate decision-bearing (repair, Friday merge).** `fp_projection_override.py` gate (d) only
   prints a banner when the newest capture is from before the 10:30 CT inactives; the 10:40 capture is a single
   attempt with a 240 s leash and "a missed capture is lost for good", after which the 10:50 build silently runs on
   Saturday's FP numbers, in which the 10:30 beneficiaries (the backup who now starts) are still priced as backups.
   That is precisely the early-game information the regulars have. Cheapest fix: a second armed capture at 10:46 CT
   (the override already takes the newest before the build) and the banner surfaced in the vetting output so a
   stale book is never uploaded unknowingly. Test: Friday's rehearsal with a planted stale capture.
2. **Screen one-setting levers on the W4 fixed-book replay that decided the tilt** (`b_w4_term_replay.sh`; no
   money-path code; an afternoon): `--mean-max-shared 5` (each row must differ from every earlier row by 4+ players:
   the direct route to "few heavy players" without an exposure cap), `--main-qb-cap-rows 4` and `3` (6–9 QBs),
   `--max-per-game 3`, and a 0.5 FP + 0.5 props `--proj-source` file (the weekly check already builds the blend
   column). Generic levers are not fitted to W1–4, so the W1–3 replays under our projections are fair out-of-sample
   checks for them too. Read: P(≥1 big), expected big seats, mean entry pct, best row. One FP week screens for "not
   worse"; it cannot prove a gain. A lever that is level on the guards and ahead on P(≥1 big) is a "preference with
   no measured cost" the operator can take for Week 5, exactly as the tilt went; otherwise it becomes a Sunday paper
   book. **Done 15:24–15:32 CT, Weeks 2–4: `reports/2026-10-06-fixed-book-lever-screen-w2-w4.md`.** The shared-player
   limit at 5 reads ahead on P(≥1 big) in Weeks 3 and 4 (.31 vs .01, .34 vs .03) and near-certain beside the base in
   Week 2 (.91 vs .93), guards held pooled; the exposure cap at 9 rows collapses P(≥1 big) in all three weeks; the
   props blend is far worse on the FP week; the QB caps move little. The live value 7 is hard-coded in the host
   script, so Week 5 needs a one-line change and Friday's rehearsal.
3. **Score the screened levers as paper books on Sunday** beside study 38 (the prereg already carries the entered
   book as a "context column, scored the same way, never an arm"; the reviewer can add context columns the same way,
   without touching the decision pair). This is the §2.2 ladder at zero cost to the frozen design.
4. **R4 replacements under FP.** If `late_inactive_swaps.py` still picks replacements by our served mean while the
   book is FP-priced, point it at the union's `proj_fp-<tag>.csv`; a 2:05 CT FP capture for the late-window
   replacements is the Week-6 version.
5. **Monday lines for W5** (information): per-line pool hit density from the monkeys; "did any entered row hold the
   slate's top-scoring game" (a one-line graph query once W5 is loaded); exact copies per entered row; the ownership
   information line by position (22a) starting now as descriptive, since the graph says the information sits at WR/TE.
6. **The contest plan is his call**: dropping the two classes where regulars hold 28–54% of entries ($4,444 and FFWC)
   lowers rows needed and changes PLAN_SHA, so it fits only if decided before Friday's re-verify.

Not this week: the finish model (§4.2), a consensus leg (no capture yet), the salary band (O-15), late swap, the TD
ledger (Addendum 89).
