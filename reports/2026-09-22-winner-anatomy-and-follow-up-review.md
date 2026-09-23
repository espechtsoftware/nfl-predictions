# Winner anatomy for the corpus, and a review of the follow-ups

**2026-09-22, evening.** This is the second external-review document. It follows
`2026-09-22-external-review-suggestions.md`.

- **§1–2** analyse the winners and top finishers of both 2026 Sundays and of 69 historical
  Millionaires, and ask what our candidate pool (the corpus) should contain that it does not.
- **§3** reviews what the team has done with the first review since this afternoon.

Every number comes from the scripts in `reports/lab-handoffs/2026-09-22-external-review/winner_anatomy/`
(README there). The data are read-only warehouse pulls, kept outside the repo; user names are never
printed. Nothing touched the money path.

---

## 1. Summary

**The corpus gap is composition, not ceiling.** Top finishers in every large 2026 field, the users whose
edge persists from one week to the next, and 69 historical Millionaire winners all share one shape. It
has four parts:

- a **chalk core**: at most one or two players under 5% ownership and at least one at 20%+;
- **full salary**;
- **two or more $7k+ players**;
- **a QB with one or two of his pass catchers**.

Our generator almost never produces that shape. In Week 2, 7% of our 12,555 candidates had a chalk core,
against 85–87% of the top 0.1% and 74% of historical winners. Across 72 historical slates, the rare
replay-book lineups that did have one scored about 8 points more per lineup at the same projection. That
holds even when ownership is predicted before lock.

| | field | top 0.1% | historical winners (69) | our Week-2 pool | our entered rows |
|---|---:|---:|---:|---:|---:|
| chalk core (≤2 players under 5% owned, ≥1 at 20%+) | 59–68% | **85–87%** | **74%** | **7.2%** | 40–48% |
| strict chalk core (≤1 under 5%, ≥2 at 20%+) | 26–35% | 50–65% | 32% | 0.3% | 10–16% |
| 3+ skill players under 5% owned | 31% | 11–13% | 20% | **90%** | 42% (W1) |
| salary used ≥ $49,500 | ~95% | 95–98% | 97% | **62%** | 86–100% |
| legal under the house stack rules | 15–18% | 12–47% | **12%** | 100% | 63–100% |

Ranges cover the two Millionaires plus the other large field each week (Play-Action in Week 1, Flea
Flicker in Week 2).

**For the corpus, in order:**

1. **A chalk-core boom sleeve.** Solve per-world optima subject to at most 1–2 skill players under 5%
   *predicted* ownership and at least one at 20%+ predicted. A walk-forward ownership model built only
   from our own pre-lock features reaches a within-slate Spearman of 0.75–0.81 against actual
   Millionaire ownership, so this needs no outside data.
2. **Salary ≥ $49,500 in the boom solves**, part of the same envelope.
3. **Only then**, and inside that envelope, a sleeve with a relaxed stack (QB + 1 pass catcher, no
   bring-back required).

Shadow it in Week 3, test it on the replay panel, and only then decide (§4).

**On the team's follow-ups (§3):**

- Most of the review was taken up quickly and well. The cross-repo lever test found a real defect: the
  integration branch lacked the deployed code.
- I disagree with two conclusions:
  - "Every crowd/paid signal is too small to change which lineups win." It was measured with player-level
    MAE and salary-blind top-k, and the lineup level says otherwise.
  - "The market bias is level, not ranking." For a salary-constrained, multi-position optimizer, a WR
    bias that grows with salary is a ranking bias.
- Process concerns: P_MIX judged on two live weeks; `MAX_PER_GAME=4` flipped before its own panel;
  Route Share weekly reads without a stopping rule; the L01 decision metric.
- New defect: the production ownership shadow is anti-correlated with actual ownership (−0.11).
- Correction to my own review: its live-2026 ownership input used the slot-grain MAX. Re-run with
  slot-summed ownership, nothing moves (Week 1 ρ +0.087, was +0.086; Week 2 +0.014, was +0.017).

---

## 2. What top finishers have that our corpus does not

### 2.1 Structure lifts in the real fields, both weeks

**Data.** 1,294,330 lineups from seven contests:

- Week 1: Millionaire (831,028) and Play-Action (158,302).
- Week 2: Millionaire (172,692), Flea Flicker (83,200), Huddle, Pylon and Nickel.

Every lineup parsed. Each lineup's score, rebuilt from its players' points, matches the recorded score
exactly.

**Measure.** Lift is the share of a finishing tier divided by the share of the field. The table is the
two Millionaires; each cell is top 1% / top 0.1%.

| feature (value) | W1 field | W1 lift | W2 field | W2 lift | both weeks? |
|---|---:|---:|---:|---:|---|
| players < 5% owned: 0 | 17% | 1.93 / 1.92 | 14% | 1.90 / 1.63 | **yes** |
| players < 5% owned: 1 | 27% | 1.30 / 1.39 | 27% | 1.25 / 1.36 | **yes** |
| players < 5% owned: 3+ | 31% | **0.46 / 0.36** | 31% | **0.52 / 0.41** | **yes** |
| players ≥ 20% owned: 0 | 19% | 0.50 / 0.32 | 15% | 0.23 / 0.00 | **yes** |
| players ≥ 20% owned: 2 | 27% | 1.47 / 1.69 | 33% | 1.20 / 1.31 | **yes** |
| naked QB (no same-team WR/TE) | 19% | 0.52 / 0.36 | 17% | 0.71 / 0.39 | **yes** |
| salary left > $1,000 | 2% | 0.37 / 0.21 | 1% | 0.69 / 0.00 | **yes** |
| no player at $7k+ | 8% | 0.49 / 0.34 | 4% | 0.01 / 0.00 | **yes** |
| QB + 2 same-team WR/TE | 26% | 1.47 / 1.48 | 26% | 1.16 / 1.08 | yes, mild |
| 5 players from one game | 7% | 2.21 / 1.85 | 5% | 0.63 / 0.32 | no: shootout bet |
| 2+ bring-backs | 8% | 2.43 / 2.09 | 7% | 0.48 / 0.18 | no |
| two TEs | 21% | 0.75 / 0.44 | 17% | 2.31 / 3.21 | no: Schultz week |
| late-window players 5–6 | 16% | 0.27 / 0.12 | 21% | 1.74 / 1.77 | no: where the shootout was |

**Replication.** The Play-Action and Flea Flicker fields reproduce every "yes" row. For example, 3+
players under 5% owned has a lift of 0.44 / 0.45 in Play-Action and 0.43 / 0.51 in the Flea. The
flipping rows are slate stories: which game erupted, which TE hit. They are not construction rules.

### 2.2 Where our corpus sits

Share of lineups, Week-2 Millionaire:

| | field | top 0.1% | our 12,555 candidates | our 97-row book (31 in these contests) |
|---|---:|---:|---:|---:|
| 3+ players under 5% owned | 31.3% | 12.8% | **89.9%** | 48% |
| 0–1 players under 5% owned | 40.2% | 58.1% | **1.4%** | 23% |
| no player ≥ 20% owned | 15.0% | 0.0% | **36.3%** | 19% |
| salary left $500–1,000 | 5.5% | 2.3% | **44.0%** | 7% |
| 5+ distinct games | 92% | 98% | 75% | 48% |

Week 1 had no archived pool on this host. Our 57 entered Week-1 Millionaire rows had 3+ players under 5%
in 42% of rows (field 31%, top 0.1% 11%), and no 20%-owned player in 42% (field 19%, top 0.1% 6%).

**Why the pool looks like this.** A boom lineup is the optimum of one simulated world, and in any world
some cheap, low-owned players spike. So world-optima are made of fringe spikes. The August anatomy found
per-world optima carry about three players above their realized three-season maximum. A lineup that needs
three specific fringe players to spike together rarely finishes on top. Human top finishers get there
with chalk that hits plus zero or one leverage piece.

### 2.3 It is not just projection in disguise

Within quintiles of the lineup's projected total (our served projection), the top-1% rate by number of
sub-5% players, in the highest projection quintile:

| contest | 0 players under 5% | 3+ players under 5% |
|---|---:|---:|
| W1 Millionaire | 1.20 | 0.30 |
| W2 Millionaire | 2.04 | 0.04 |
| W1 Play-Action | 1.05 | 0.55 |
| W2 Flea | 1.59 | 0.00 |

In the upper two quintiles of every contest, which is where our lineups live, 0–1 sub-5% players beat 3+ by a wide margin.
Inside our own Week-2 pool, realized mean points fall steadily with the count: 109.6 with one sub-5%
player, 97.6 with three, about 90 with four or more. The 99th percentile falls from 171 to 152.

### 2.4 The 72-slate test on our own books

**Setup.** The replay books (`replay_lineups_pitk1`, 80 lineups per slate, 2022–25) scored against each
slate's book mean. The model is realized ~ projection + a bucket for the number of skill players under
5% owned, with slate-clustered standard errors.

| ownership used to count sub-5% players | share of book with 3+ | 0–1 vs 3+ | 2 vs 3+ |
|---|---:|---:|---:|
| actual Millionaire ownership (post-lock) | 78.9% | **+8.87** (se 2.30) | +7.47 (se 1.07) |
| LineStar projected ownership (last updated after the slate, per production) | 83.5% | +6.87 (se 2.19) | +4.88 (se 1.30) |
| **walk-forward model from our own pre-lock features** | 88.3% | **+8.19** (se 1.57) | +2.57 (se 1.87) |

**The model.** LightGBM on position, salary, projection, value and its within-position ranks, p90,
implied team total and market points, trained on earlier seasons only. Within-slate Spearman with actual
ownership: 2023 0.752, 2024 0.806, 2025 0.805. The 2022 predictions are a backcast used only in the book
test.

The counting threshold is predicted ownership, so this is the version a generator can use before lock.

**Caveat.** This measures the *average* book lineup, not the book's best. The tail evidence is §2.1 (the
top 0.1% and top 0.01% lifts) and §2.6 (the winners).

### 2.5 Users whose edge persists build this way

**Does skill persist?** For 721 users with 20+ Millionaire entries in both weeks, their mean finish
percentile in Week 1 predicts Week 2: Spearman +0.116, p 0.002. Modest, but real. Define "skilled" as a
user's top 20% in one week, then describe their lineups in the *other* week:

| described on | own. sum (skilled / other) | players < 5% | rows with 3+ < 5% | $7k+ players | salary left |
|---|---|---|---|---|---|
| W2 (skill from W1) | 125.8 / 117.0 | 1.72 / 2.00 | 25.5% / 33.4% | 2.04 / 1.93 | $114 / $138 |
| W1 (skill from W2) | 127.6 / 114.5 | 1.28 / 1.75 | 14.4% / 26.6% | 2.04 / 1.83 | $151 / $154 |

**Stacking does not separate them.** Stack depth, bring-backs, max per game and naked-QB share are
identical to the second decimal. Their edge is *which players*, not *which shapes*.

### 2.6 69 historical winners

This is the registry: 2019 and 2023–25 Millionaire winners, joined to box scores for teams (96% of rows
matched).

- **House rules.** Only **12%** of fully matched winners are legal under them. The August anatomy found
  43 of 51.
- **Stack depth:** 0 in 18%, 1 in 48%, 2 in 32%, 3+ in 2%.
- **Bring-back:** none in 60%.
- **Max players from one game:** ≤2 in 30%, 3 in 40%, 4 in 24%, 5 in 6%, 6+ never. So 94% fit the new
  `MAX_PER_GAME=4`.
- **Chalk core:** 74%, between 71% and 76% in every season. Strict version 32%.
- **Salary:** 97% used at least $49,500.
- **Studs:** 64% had 2+ players at $7k+.

**Nuance.** A single winner carries about as many sub-5% players as a random field lineup: 1.65 against
1.49 across 52 slates with full ownership. The strong tilt in §2.1 appears at the top 0.1% and top 1%,
not in the one lucky winner. The decisive comparison is with our corpus: 20% of winners had 3+ sub-5%
players; our books had 79–88% and our pool 90%.

### 2.7 What to put in the corpus

In order. Each item is a nomination to test, not a rule to enter.

1. **Chalk-core boom sleeve (primary).** A share of the boom solves adds two constraints in *predicted*
   ownership space:
   - (# skill players under 5%) ≤ 1, with ≤ 2 as a second arm;
   - (# players ≥ 20%) ≥ 1.

   The world objective is unchanged, so the simulator still picks which chalk and which single leverage
   piece. It needs a live ownership model; the §2.4 model is the starting point (see §3.2 on why not
   `own_shadow`).
2. **Salary ≥ $49,500 for boom solves.** 38% of Week-2 candidates left $500+ unused, against 2–5% of
   top finishers and 3% of winners. That is largely a symptom of fringe spikes, so it belongs in the same
   envelope rather than as a separate lever.
3. **A relaxed-stack sleeve, only inside the chalk envelope** (QB + ≥1 same-team pass catcher,
   bring-back optional). Earlier relaxed sleeves (016, PREREG-053/055) were tested in the fringe-heavy
   boom regime, so they do not answer this question. Test it after item 1, not with it.
4. **Keep** `MAX_PER_GAME=4`: 94% of winners and 98% of the Week-2 top 0.1% comply.
5. **Do not** encode bring-back counts, 2-TE builds, late-window share or game concentration. They flip
   between slates.
6. **Receipts.** Add to every build receipt the corpus shares from §2.2 (sub-5% count, 20%+ count,
   salary left, house legality), so Monday's scoreboard can compare the corpus, not only the book, with
   the field.

**Why this is not a closed item.** The ledger's ownership-related verdicts used `own_est`, the naive
value softmax. It correlates 0.10 within a slate with real ownership, so those arms had no ownership
information. The August ownership-template arm proposed the *opposite* template ("4 players under 10%")
from the lone winners. That draft was never frozen because it depended on `own_est` calibration.

---

## 3. Review of what the team did since the first review

### 3.1 Done well, and accepted

- **Finding A was reproduced exactly** and the regime-flip conclusion withdrawn. The reviewer document
  (C2) was rewritten.
- **The cross-repo lever-consumption test** found that the integration branch lacked the deployed
  project-slate code (a deploy would have silently dropped four levers). It was merged at source-set v11,
  and the test is now in the money lane. This is the most valuable thing done today.
- **The Monday scoreboard** was built. Its Week-1 and Week-2 reads are useful: Week 1 book +7.1 against
  the field; Week 2 −17.2, with 8.9 of the book's +9.0 projected edge coming from the fixed stand-ins.
- **Other measurements:**
  - active-only Q ratio: 0.904;
  - market-conversion bias: RB +1.0 to 1.6, WR up to +2.5 at 18+;
  - the sampler gate passed on Week 2;
  - the §5.3 floors: accepted as not decision-relevant.
- **The laptop's ownership-grain find** was real. It touched my review's §3.3 input; the re-run changes
  nothing material.
- **P_MIX and PG_AWARE were built as default-off flags**, and the Q-haircut interaction was flagged.

### 3.2 Where I disagree

1. **"Every crowd/paid signal is real but too small to change which lineups win."** The evidence behind
   this was player-level MAE and salary-blind top-k pick quality, both of which dilute a composition
   effect.
   - At lineup level, the same information separates lineups by about 8 points at equal projection
     (§2.4). It moves top-0.1% lifts from 0.4× to 1.4–1.9× in all four large contests (§2.1–2.3).
   - The generator puts about 90% of the corpus on the losing side (§2.2).
   - The operator's follow-on, "remaining 2026 effort goes to the pool's ceiling supply", aims at the
     wrong target. In Week 2 the pool's lineups with the full target shape (chalk core, full salary, 2+ studs,
     QB stack) also had the higher ceiling (p99 171.5 vs 155.8).
     Ceiling through composition is testable this week; ceiling through dose has already been paid for
     in the ledger.
2. **"Market bias is level, not ranking."** The served WR bias grows with the line: +0.8 / +0.6 at 6–10
   points up to +3.0 / +1.6 above 18 (2023 / 2024). A salary-constrained optimizer trades WRs against RBs and studs against
   value. A bias that is largest for the most expensive WRs therefore pushes it off them, which is
   exactly the post-mortem's under-holding of Smith-Njigba (5%) and Lamb (9%). Top-k realized points
   ignore salary and flex, so they cannot see this. The test is at lineup level: re-optimize the replay
   books with a bonus-aware conversion, then score them with the scoreboard decomposition.
3. **Production's ownership shadow is broken.**
   - `nfl_predictions.own_shadow` for 2026 Week 1 (its latest run, 2026-09-10) covers 53% of the players
     and sums to 500% (not 900%).
   - It has a within-slate Spearman of **−0.11** with actual Millionaire ownership.
   - Anything that uses it (`OWN_MODEL`, the leaderboard's projected ownership, a future chalk sleeve)
     needs the model rebuilt first. The grain fix on `laptop/ownership-grain-20260922` is necessary but
     not sufficient.
   - LineStar's pre-lock page returns 10 of 813 salaries without a login. The §2.4 model, built from our
     own features, reaches 0.75–0.81 and removes that dependency.

### 3.3 Process concerns

4. **P_MIX is being judged "judge-only on the 2026 W1/W2 live pools".** That is n = 2 again, for a lever
   whose standing evidence is 216 slate-banks. The decision belongs on the historical panel, against the
   four live availability rules as the control. The two live weeks can illustrate, not decide.
5. **`MAX_PER_GAME=4` went live before the panel built to test it (L01) had been read.** It rests on a
   two-slate, five-strategy screen of realized outcomes. Substantively the risk is low: §2.6 shows 94%
   of winners comply. The cost is the shootout lineups, which were 15% of Week 1's top 0.1%. Record it as
   adopted on thin evidence, with L01 as the check.
6. **The L01 decision rule** (selected ≥194 clears ≥ CTRL, and mean pool oracle > CTRL in 3 of 3
   seasons) reads tail counts and a hindsight oracle. The programme itself deprecated both: tail counts
   are too rare to decide on, and the oracle is not retrievable. Keep the frozen rule, but report two
   secondaries beside it:
   - the scoreboard decomposition on the replay books;
   - the finish percentile against real 2022–24 Millionaire ownership.
7. **Route Share weekly reads.** "If the treatment keeps winning, the operator may switch it on" is a
   sequential rule on best-of-80 realized differences, with no declared stopping rule or error rate.
   Declare it before Week 3's read, or it becomes noise-chasing.
8. **The Questionable haircut stays at ×0.80 for Week 3** because "the entered books are built
   Saturday". But the Saturday build pairs ×0.80 (which assumes zero points if the player sits) with a
   Sunday replacement step (which gives most of that value back). The consistent Saturday factor is
   about 0.84 × 0.904 + 0.16 × (replacement value, about 0.8), which comes to about 0.89. This is small,
   and the operator's call.
9. **The scoreboard omits the heavy-user benchmark** I suggested (the 51–150-entry cohort). Given §2.5,
   that cohort's average lineup is the more informative bar.

---

## 4. Suggested next steps

| when | what | cost |
|---|---|---|
| before Sunday (paper only) | Fit the §2.4 ownership model on the Week-3 frame. From the live pool, select a chalk-core DEMAX shadow book (candidates with ≤1 predicted sub-5% player) and score it Monday next to the entered book. | one script; no money |
| Monday | The scoreboard with the corpus shares (§2.2 table) and the heavy-user benchmark | small |
| this week | Replace `own_shadow` with a walk-forward model (§2.4). Gate it on within-slate Spearman ≥ 0.7 against 2025 actuals. | small |
| next lab slot | Chalk-core boom sleeve vs control on the replay panel (2022–25, Millionaire ownership available). Primary: finish percentile against the real ownership field; secondaries: the scoreboard decomposition and the ledger proxy. Freeze before any read. | one panel |
| after that | A relaxed-stack sleeve inside the chalk envelope; a bonus-aware market conversion at lineup level | one panel each |

## 5. Limits

- Two live slates. The field lifts are strongest where they replicate across both weeks and a second
  contest each week, and the winner registry adds 69 slates at the single-winner level.
- The field and registry analyses use **actual** (post-lock) ownership. The actionable version rests on
  §2.4 (predicted ownership, +8.19, se 1.57). It is measured on the average book lineup, not on the
  finish of a book built by a chalk-core sleeve. That is what the proposed panel tests.
- The Week-1 pool is not on this host, so Week-1 corpus shares come from our 57 entered rows.
- User skill persistence is modest (ρ 0.116). The skilled-cohort differences are consistent in both
  directions, but small in points.
