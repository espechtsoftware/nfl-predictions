# Scoring suggestions after Week 3: what the new configuration still leaves on the table

**Date:** 2026-09-28 (Monday after Week 3). **Author:** Claude, remote session, branch
`claude/draftkings-lineup-strategies-cjlxo0` (fast-forwarded onto `production/week3-integration-20260921` @ `914e8255`).
**Asked for by the operator:** pull the latest commits, review the post-mortem and the steps taken since, and write up
suggestions to improve scoring.

**What was read.** The 209 integration commits since my 09-25 review; `reports/2026-09-27-week3-post-mortem.md`; the
external review on `review/week3-review-20260928` (`5ac250a6`); the laptop's critique of the Week-4 plan; the class-gates
evidence; the L04, L05, L09, L10, L11, L12 reads and PREREG-L13 / PREREG-O1; the vendor-signals audit; the R2(a)
replication that killed my recency idea; the Week-4 operating handoff and the HANDOFF entries of 09-27/28; the lab's
`two_track.py`, `class_selector.py` and the T-70 rules in `cascade_adjust.py`.

**Status:** nominations only. Nothing here touches the money path, a frozen cohort or Week 4's armed configuration.
Four small checks were run on the public panel from 09-25 (§2); scripts in `reports/lab-handoffs/2026-09-28-scoring-suggestions/`.

---

## 0. The short version

**What changed, in one paragraph.** Week 3 lost 204 entries in 45 contests for one satellite ticket. The post-mortem found
the expected-max selector doing worse than random inside its own pool, and Sunday builds beating the Saturday book both
weeks. The external review corrected the yardstick: satellites pay the top 0.2–9% of their fields, not an average
lineup, and at the rake paid a field-average book loses 9–16% a week while the best measured selector (MEAN) clears
satellite lines at about 0.9× the field's rate. Week 4 is armed as: a mean selector everywhere, a mean-selected sleeve
dealt to the deep-line contests, a class-shape sleeve on half the boom visits, the Sunday T-70 build as primary with no
lev batch, three T-70 projection rules, a 25% DST cap, MIN_PROJ, the late-inactive replacement, and a score-based
satellite late swap entered on the operator's decision despite a NOT SUPPORTED read. PREREG-L13 (selectors at p99 and the
plain-mean optimizer) is running; O1 (Fantasy Points ownership vs the lag model) is prospective from Week 4.

**Where I agree.** The two-track diagnosis, the real-line yardstick, the economics table, the Sunday build, MIN_PROJ, the
DST cap, the fail-loud audit, the one-paper-week rule, and the class *sleeve* (its Week-1 gate is genuinely out of
sample). The R2(a) kill of my recency fade was correctly applied under its pre-declared criteria.

**Where the new configuration still leaves scoring on the table** (§3, ranked):

| # | suggestion | why now | cost | earliest |
|---|---|---|---|---|
| S1 | **Variance-aware selection for the p99 contests** (a new lab panel, "L14"): P(≥ p99) arms with an *empirical* Gaussian (the residual correlation card and band SDs) beside the simulator's worlds and MEAN | At p99 a 10% larger lineup SD is worth ×1.6 in tickets, as much as +5 points of mean; L09's null for P(≥line) was at p89 where SD barely matters (×1.14); L13 has no variance arm | small (L13's harness) | panel this week; paper Week 5 |
| S2 | **A public-projection news channel at T-70**: snapshot RotoWire (Sleeper), ESPN and FantasyPros projections Saturday and at 10:35 CT; use Saturday→T-70 deltas as a re-projection signal and as a third component where no prop exists | The model does not reprice on news (Sadiq 7.5 → 26.5); human-edited projections do, and LineStar's PP already explains ~27% of the crowd's edge historically | small; free | capture Week 4; paper Week 5 |
| S3 | **Unblock the ownership predictor now**: LineStar's projected ownership (free; the backfill already fetches and discards it) beats the lag model by +0.03–0.04 Spearman on 2023–25, exactly L05's reopening bar; add it as a third O1 arm and run the historical L05 reopening test this week; add `surprise_prev` to the lag model regardless of R2(a) | L05 cell C: the predictor, not the sleeve, is the bottleneck; O1 waits until Week 7 | small | this week |
| S4 | **Allocation: the top rows should repeat across the 11-entry satellites**, or at least cycle the top four; quantify the variance trade on the rehearsal tool | Expected tickets are additive and P(≥ line) is convex in the mean below the line; the sat20 grinders enter one lineup 19 times; the reviewer already adopted repetition for the deep lines | none (a setter rule) | Week 4 if the operator accepts the variance |
| S5 | **Guard the boom-only Sunday pool's mean** in Wednesday's smoke; if its top-144 projects below the Saturday lev+boom pool's 130.6, put plain-mean-optimizer rows into the Sunday pool as lev's replacement (3 minutes; weakly dominant under MEAN) | Lev rows averaged 137 projected vs 116 for boom; lev was dropped from the Sunday build | small | Wednesday |
| S6 | **Class model v2**: train on every ticket-line field (satellites, supersats, FFWC), with per-line targets, more weeks, regularization, and the market sum beside the model sum; a low-noise auxiliary target, "entered by a 20+-entry user" | The selector failed Week 1 out of sample on a 2-week fit; the fields are the asset and nothing on the money path reads them | medium | paper from Week 5 |
| S7 | **Shrink toward the market where the model is optimistic**: PREREG-L04b (model weight 0.30, 0.15) and a row-level penalty on Σ max(model − market, 0) | L04's ordering is monotone in market weight; the busts were model-above-market; the player-level market floor was nil, so the lineup-level form is the untested one | small | L04b next week |
| S8 | **Minimum viable Sunday**: a written order of what may fail and what stands, and no further entry-path changes this week | Week 2 was lost to defects; Week 4 changes host, generator, selector, layout, three projection rules, and adds two afternoon tools | none | now |
| S9 | Contest economics: the reviewer's R6/R7 stand; two additions on field softness and the $2 circle | | | operator |
| S10 | DST: a market-anchored projection; Kalshi D/ST fantasy lines are being captured | Three of the five heaviest exposures were DSTs that busted; DST is a constant in every world | small–medium | Week 5+ |

**What not to do:** re-test MAXGAME5 or the tilt without a new predictor; fade ownership; add a fourth objective; adopt
anything else on a rehearsal number this week.

---

## 1. Reading the post-mortem, the review and the plan

### 1.1 What is right and stays right
- **Selection by expected max cost the satellites.** MEAN beat EMAX on two independent 72-slate-bank panels (+13.3%,
  +20.8% tickets at p89) and on both clean live weeks (+23, +31 points per lineup). The historical expectation is +2.9
  points per lineup, lumpy: paired 30–32 and 37–28.
- **The lines were mis-stated and are now right.** Satellite tickets sit at p91–p99.8; half the satellite stake sat behind
  p99 lines where nothing had been measured. L13 measures them.
- **Sunday beats Saturday**, mostly by removing inactives; the T-70 rules are the first attempt at the rest.
- **The tilt figure was hindsight**, caught in time; L12 is inconclusive at +1.8%.
- **The class sleeve passed out of sample** (Week 1: 3.5% vs 1.0% of rows at 193+); the class selector did not (8 vs 31
  paid). Adopting the sleeve and papering the selector is the right split.
- **The economics.** At 0.9× the field's ticket rate and 9–16% rake, the system loses in expectation. Break-even needs
  1.10–1.19× the field's rate. Each +1 point of true lineup mean is worth about +6% tickets at p89 and +10% at p99
  (§2.1), so the gap to break-even is roughly +3–5 points per lineup, or the variance equivalent.

### 1.2 Three things the plan still gets wrong or leaves open
1. **The p99 contests are treated as mean problems.** The mean-selected sleeve takes the deep lines because P(≥line) and
   EMAX "measured below the mean at every real line on the Week-3 pool". That was the *simulator's* P(≥line). §2.1 shows
   that at p99 the lineup's variance is as valuable as its mean; §2.3 shows player residual SDs range from 5 to 11, so
   lineups differ in variance by a lot. The open question is whether variance can be *ranked* without the simulator's
   dependence errors. L13 does not ask it (S1).
2. **The Sunday build's supply changed under the selector.** Lev is gone (item 6), so the mean track now selects from
   boom rows whose projected means averaged 116 against lev's 137. The reviewer's plain-mean optimizer is the natural
   replacement and it is a paper arm that "slips first" (S5).
3. **The information layer is still the model plus a fixed bump.** The T-70 vacated bump is a constant table (+1.6 RB/TE,
   +0.7 WR, +1.0 other) from one census; the crowd re-prices news continuously and public projections are edited by
   hand on Sunday morning. Nothing in the plan captures a second opinion at T-70 (S2).

### 1.3 On my 09-25 suggestions, honestly
- **R2 (fade the recency part of ownership) was killed**, correctly: on our own projections the chased part carries a
  weak but detectable signal (ρ +0.027, t 2.0 against the pre-declared |t| < 2). What survives is the *predictor* half
  of R2, which the kill did not test (S3).
- **R1 (select on Sunday information)** became the Sunday build as primary. The R1(c) paper (Saturday pool re-selected on
  T-70 banks with `dual_emax`) was built but its Monday outcome is not in HANDOFF; the post-mortem's mean re-selection of
  the Saturday pool on Sunday projections scored 148.3. Under MEAN the question is moot: build on Sunday.
- **R10 (IC/TC lines)** landed in the scoreboard; **R11 (flex latest)** went live; **R5 (Kalshi)** is capturing and
  carried no signal in Week 3 (median MAE 5.87 vs 5.76); **R3 (eruption count)** and **R4 (books, de-vig)** are queued behind the Week-4 build.
- My "no slate factor" and "opponents' fantasy output couples through script" findings fed the post-mortem's Q10 (Vegas
  pace, cross-team coupling), still untested.

---

## 2. Four quick checks (public panel from 09-25: 74 LineStar main slates 2022–26 W2, nflverse box scores)

Scripts: `reports/lab-handoffs/2026-09-28-scoring-suggestions/`. Third-party data stays outside the repo.

### 2.1 Mean versus variance at each ticket line (`a_line_arithmetic.py`)
Gaussian lineup scores; field p50 127, SD 27 (the Millionaire's p89 160 and p99 189 both give SD ≈ 27); a row with mean
135.

| line | P(row ≥ line) | +1 point of mean → | +10% of row SD → |
|---|---:|---:|---:|
| p89 (160) | 15.9% | ×1.06 | ×1.14 |
| p95 (171) | 7.3% | ×1.08 | ×1.28 |
| **p99 (190)** | 1.4% | ×1.11 | **×1.63** |
| **p99.8 (205)** | 0.26% | ×1.13 | **×2.13** |

- At p89, MEAN is nearly the right objective: variance is worth little, which is why L09's P(≥line) arms and MEAN were
  within 2% of each other and why the mean track is right for the $2 and 594-entry satellites.
- At p99 and p99.8, where about half the satellite stake sat in Week 3, a 10% SD difference is worth as much as +5
  points of mean. The selector for those contests should trade mean for variance, *if* variance can be ranked.
- Structure alone moves the SD only a little: nine independent players at residual SD 8.5 give 25.5; a QB+2 stack adds
  about 2 (QB–WR ρ +0.38/+0.36); a bring-back adds 0.5. Player choice moves it more (§2.3).

### 2.2 The ownership predictor: LineStar's projected ownership vs the lag model (`b_ownership_predictors.py`)
Within-slate Spearman with realized Millionaire ownership, mean over 18 slates a season:

| season | LineStar projected ownership (all / skill) | the lag model (walk-forward, HANDOFF 09-23) |
|---|---|---|
| 2023 | 0.779 / 0.777 | 0.751 |
| 2024 | 0.805 / 0.808 | 0.768 |
| 2025 | 0.781 / 0.797 | 0.767 |

+0.028 / +0.037 / +0.014 (skill only +0.026 / +0.040 / +0.030): at or above L05's ≥ +0.03 reopening bar in two seasons of
three, with no back-capture problem (the payload is what `linestar_backfill.py` already fetches). A blend of the two
predictors, which use different information (LineStar's editorial model; our lags and salary deltas), is the obvious
candidate to clear the bar in every season. Caveat carried from HANDOFF 09-22: LineStar's historical periods were last
updated after each slate, so the projected-ownership field's pre-lock status cannot be proven historically; the 2026
W1/W2 values (0.73 all, 0.81 skill) were captured live.

### 2.3 Player residual SD is heterogeneous, and the top band over-projects (`c_residual_sd_and_bias.py`)
Residual = actual − LineStar projection, all main-slate rows with projection ≥ 4:

| position | SD by projection band 4–8 / 8–12 / 12–16 / 16–20 / 20+ | mean residual 16–20 / 20+ |
|---|---|---|
| QB | 2.8 / 8.2 / 7.4 / 8.2 / 8.9 | +1.0 / −0.5 |
| RB | 6.2 / 7.0 / 8.2 / 9.0 / 10.4 | −0.4 / −2.2 |
| WR | 5.9 / 7.3 / 8.6 / 10.2 / 10.8 | −1.2 / −2.5 |
| TE | 5.3 / 6.9 / 7.5 / 9.5 / 9.0 | −0.7 / −5.2 |

- SDs run from 5 to 11: a lineup of high-band WR/RB has an SD near 30, a lineup of mid-band TEs and RBs near 22. That
  is the ×1.4–1.6 lever at p99 in §2.1, if the selector can see it. The simulator's per-player marginals (TabPFN
  quantiles) carry this part; its dependence does not.
- The top projection band under-delivers by 1–5 points (the projection is unbiased overall: 9.80 vs 9.81). That is the
  optimizer's curse at player level, the same shape the laptop found in the fields (top-1% lift falls from 2.0 at the
  80–95th projection percentile to 0.5–0.7 at the 99.5th).

### 2.4 A replay of the obvious fixes: null (`d_calibration_replay.py`)
56 slates (2023–2026 W2), 20 lineups per slate per arm, DK Classic rules, $49–50k, pairwise overlap ≤ 7, realized points;
walk-forward isotonic calibration of E[actual | projection] by position fitted on prior seasons.

| arm | projected / realized mean | best | rows ≥ 170 | rows ≥ 190 |
|---|---|---|---|---|
| RAW top-mean | 141.7 / 129.0 | 155.7 | 1.07 | 0.27 |
| CALIBRATED top-mean | 138.1 / 129.5 (+0.4, t 0.2) | 154.6 | 1.12 | 0.18 |
| CALIBRATED + 0.35 × band SD ("ceiling") | 138.3 / 129.8 (+0.8, t 0.3) | 155.6 | 1.02 | 0.23 |

- **Band calibration and a linear ceiling term do not move a top-mean book.** Monotone re-scaling barely changes what
  the optimizer picks, and a linear "mean + κ·SD" objective is not the same as P(≥ line). The variance test has to be
  done at the line, on lineups, as in S1.
- **The lineup-level winner's curse is 9%**: the top-20 rows by projection realize 129 against a projected 142 (the
  projection is unbiased on average). Anything that selects the extreme top by one projection pays this; the market as
  a second opinion (S7) and pooling (S2) are the defences.

---

## 3. The suggestions

Format as before: mechanism, evidence, change, test, kill, prior.

### S1. Variance-aware selection for the p99 contests ("L14") — *class S; panel this week; paper Week 5*
- **Mechanism.** For a flat-payout contest whose line L sits at the field's p99, expected tickets = Σ_rows P(row ≥ L),
  and P(row ≥ L) ≈ Φ((μ − L)/σ). At z ≈ −2 the derivative in σ is as large as in μ (§2.1). The mean selector ignores σ;
  the simulator's P(≥L) carries σ but with the wrong dependence (WR1–WR2 +0.277 vs +0.02 real; TDs independent) and
  hard-capped tails, so its ordering at p89 was no better than MEAN (L09).
- **Change.** A third estimate of P(row ≥ L) from an **empirical Gaussian**: μ = projected sum; σ² = Σ σ_j² + 2 Σ ρ_jk σ_j σ_k
  with σ_j from the served p10/p90 (or position × band SDs, §2.3) and ρ from the residual correlation card of 09-25
  (QB–WR1 +0.38, QB–WR2 +0.36, QB–TE +0.29, QB–opp QB +0.24, WR–WR ≈ 0, RB–opp RB −0.08). Select top-K by that P at the
  contest's own line. Two variants: Gaussian, and a lognormal-ish skew (the exponential upper tail above 35 from 09-25).
- **Test.** L13's panel and harness; arms MEAN, EMAX, PMO, SIM-P(≥p99), EMP-P(≥p99); tickets at p99 and p99.8 primary,
  p89 co-reported (it should lose a little there). Then a paper track for the p98+ contests beside the mean sleeve.
- **Kill.** EMP-P(≥p99) ≤ MEAN at p99 on both seasons. Then the mean sleeve is right for the deep lines too.
- **Prior.** L09's PL arms (simulator worlds, p89 only); the reviewer's "P(≥line) worse than mean at every real line"
  (simulator worlds, Week-3 pool); the covariance work of 09-25. No panel has tested a non-simulator variance estimate at
  p99.

### S2. A public-projection news channel at T-70 — *class C; capture from Week 4; paper Week 5*
- **Mechanism.** The model repriced nothing when Mason Taylor was ruled out; the T-70 rules now add a constant (+1.6 TE).
  Human-edited public projections (RotoWire via Sleeper's API, ESPN, FantasyPros consensus) are updated through Sunday
  morning and re-price beneficiaries, game-time decisions and weather. Their *Saturday-to-T-70 delta* is a cheap, free
  news signal; their level is a third component for the 57% of rows with no prop price.
- **Evidence.** LineStar's public projection, a similar object, explains 27% of the crowd's edge over our replay
  projection historically (external review §4, ρ +0.099 to our residual; late games +0.160). Two public projections
  averaged beat either alone in all four seasons 2022–25 (r 0.543 vs 0.530/0.535; 09-25 research). Their errors
  correlate 0.956 with each other, so one or two sources suffice.
- **Change.** A capture job (Saturday after the 09:45 refresh; 10:35 CT Sunday), append-only; a T-70 paper projection
  = the served projection + w × (public T-70 − public Saturday) for players whose delta exceeds a threshold, and a
  model/market/public blend on unpriced rows. Grade weekly (MAE/CRPS and the book-vs-field IC lines) before any live use.
- **Kill.** After four graded weeks the delta carries no residual information beyond the T-70 rules.
- **Prior.** External review Finding D (LineStar PP as a blend component; not built). The 09-25 R4(d). Nothing captures
  a public projection twice on the same weekend.

### S3. Unblock the ownership predictor now — *class C; this week*
- **Mechanism.** L05 cell C: the chalk-core sleeve flips with realized ownership labels (−0.00376, both seasons) and not
  with the lag model's. The Week-3 tilt told the same story (156.8 with realized ownership, 148.1 pre-lock). Every
  ownership-aware lever (sleeve, tilt, the class model's chalk anchor) waits on a better pre-lock predictor, and O1 waits
  until after Week 7 for one vendor.
- **Change.**
  1. **LineStar projected ownership as a third O1 arm** and as a historical test now: it is free, already fetched by
     `linestar_backfill.py` (`Ownership.Projected`, keyed by the Main slate id) and discarded; §2.2 puts it +0.03–0.04
     over the lag model on 2023–25. Run L05's reopening test (walk-forward Spearman on 2023–25, ≥ +0.03) on LAG,
     LINESTAR and a LAG+LINESTAR blend this week. The harness refused the fetch on the laptop on 09-22; the operator runs
     one command.
  2. **`surprise_prev` in the lag model** (last week's DK minus last week's served projection, and its positive part).
     R2(a) killed the *fade*; it measured nothing about the *predictor*. On LineStar's base it removed a −4 pp bias on
     last week's boomers in every season with a +0.01 Spearman gain; on the lag base the gain is unmeasured.
- **Test.** L05's own reopening rule; then PREREG-L07 as drafted (informed-chalk anchor) with the winning labels.
- **Kill.** No predictor or blend clears +0.03 in each season.
- **Prior.** O1 (FP vs LAG, prospective); L05; the 09-23 lag alignment. LineStar's projected ownership appears in the
  external review (Spearman 0.784) and in my 09-25 document; nobody has run it against the lag model.

### S4. Allocation across the identical satellites — *class E; the operator's variance choice*
- **Mechanism.** Nineteen $2 11-entry satellites are nineteen independent contests. Expected tickets = Σ_c P(row_c ≥
  L_c); the row that maximises P for one of them maximises it for all. P(≥L) is convex in the mean below the line, so
  spreading rows 1–19 across the contests costs expected tickets: at p91 each point of mean is worth about 6%, and rows
  5–19 by mean sit several points below row 1. The circle of grinders does exactly this (one lineup in all 19, HANDOFF
  09-27 22:07). The reviewer adopted repetition for the deep lines ("a sleeve may repeat the main book's top rows"); the
  sat20s still take unique rows on the operator's 09-24 instruction ("make sure we're not doing the same entries").
- **Change.** Nothing until the operator sees the numbers: run `rehearsal_two_track.py` on Weeks 1 and 3 with (a) the
  current unique rows, (b) the top row in every sat20, (c) the top four cycled (each in 4–5 contests). Report expected
  tickets and the all-or-nothing risk of each. (c) keeps most of the expectation with a quarter of the correlation.
- **Kill.** (b)/(c) do not beat (a) on both rehearsal weeks.
- **Prior.** The head layout's shared top four; the deep-line sleeve. The sat20 rule is a stated preference, not a
  measurement.

### S5. Guard the Sunday pool's mean; plain-mean rows as lev's replacement — *class S; Wednesday*
- **Mechanism.** The Sunday build is now lev 0 / boom 4,800 + 2,400 class-sleeve visits, selected by MEAN. Boom rows are
  per-world optima (projected mean 116 on the Week-3 pool against 137 for lev rows); the mean track's top rows on
  Saturday came largely from lev. The class sleeve caps its rows' projected sums at the map's p95 by design. So the
  Sunday pool's top-144 by mean may project below Saturday's 130.6.
- **Change.** In Wednesday's full-size smoke, print the top-144-by-mean projected sum of the Sunday-shaped pool beside
  the Saturday D12800's. If it is lower, add the plain-mean optimizer's rows (144–300 diverse, house rules, cap 4, $49k,
  overlap ≤ 7, MIN_PROJ; 3 minutes) to the Sunday pool. Under a MEAN selector a union of pools is weakly dominant on
  projected mean; L13 separately decides whether PMO *alone* is supported at p89.
- **Kill.** The Sunday pool's top-144 projects at or above Saturday's.
- **Prior.** The reviewer's R5 (paper arm, "first to slip"); L13's PMO arms.

### S6. Class model v2 — *class S; paper from Week 5*
- **Mechanism.** The class model is the right idea: learn the line-clearing class from the real field's outcomes instead
  of from the simulator. Its selector failed Week 1 out of sample because a two-week fit carried Week 3's fashion (cheap
  QB, cheap TE). Effective sample is two slates, not 1.17M rows.
- **Change.**
  1. **Train on every ticket-line field you hold**, not only the Millionaire's top 1%: the 45 Week-3 contests, the
     Week-2 satellites, with the target "cleared this contest's line" (p91, p95, p99, p99.8), so the model learns the
     shape at the lines that pay, per contest type.
  2. **Regularize** (a C sweep by leave-one-week-out, which the fit script already prints) and weight weeks equally.
  3. **The market sum beside the model sum** as the percentile feature; our projection equals the market on accuracy and
     the class model inherits its defects (Week 2).
  4. **A low-noise auxiliary target: "entered by a 20+-entry user."** The heavy users average 132.7 vs 125.1 per entry and
     take 43–74% of the paid places; whether a lineup is a pro's lineup is learnable from shape with no outcome noise
     and 400k positives. Imitation as a regulariser, not a replacement (exploratory).
- **Test.** The Monday refit's leave-one-week-out lifts; the paper arm's tickets at real lines (already scheduled).
- **Kill.** v2's held-out lift is not better than v1's over three weeks.
- **Prior.** The reviewer's §4 and R2; the laptop's Week-1 gate; the lab's learned selectors (PREREG-096 and the KG
  reranker), which learned from our own pools and reverted.

### S7. Shrink toward the market where the model is optimistic — *class C; L04b next week*
- **Mechanism.** L04's ordering is monotone in market weight (model-only worst, 0.70 next, 0.45 best; more market weight
  untested). The Week-3 busts were "model above market by 1.4–1.6" (St. Brown, Taylor, Washington); the review found the
  one-sided *floor* nil at player level (5.826 vs 5.833 MAE). What is untested is a lower model weight, and a
  lineup-level penalty on rows built from model-optimistic players, the defence against the top-band curse (§2.3, §2.4).
- **Change.** PREREG-L04b: model weights 0.45 (base), 0.30, 0.15 at lineup level, the same reader. And a selection arm
  on the Week-1/3 pools and the L13 panel: rank by projected sum − κ × Σ max(model − market, 0), κ ∈ {0.25, 0.5}.
- **Kill.** Neither beats the base on the finish share and tickets.
- **Prior.** L04 (closed the 0.45 vs 0.70/1.00 question; nominates lower weights for a new preregistration); Addendum 15
  (flat 0.30–0.50 on the one-market substrate).

### S8. The minimum viable Sunday — *operations; now*
Week 4 changes the host, the generator (lev 0 + class sleeve), the selector, the layout, three projection rules, and adds
two afternoon tools, on the laptop's first week. Week 2 was lost to defects, not strategy. The take-over document lists
the risks; it does not rank what may fail. Suggested written order, one line each, agreed before Wednesday:
1. The 09:10 book (pre-inactives, mean selector) is the floor: it is uploaded if anything after it fails.
2. The T-70 build replaces it only if the audit passes; a refusal is a normal outcome.
3. The class sleeve is the first thing to switch off (`CLASS_SLEEVE_EVERY=0`) if Wednesday's smoke is slow or the
   sleeve's projected band is empty on the Week-4 frame.
4. The late-inactive replacement (R4) runs; the satellite late swap runs only if the TNF dry run passed end to end
   including the edit upload, and only on rows the receipt marks flat-payout.
5. No other entry-path change enters this week, whatever Monday's paper numbers say (the reviewer's own rule).

### S9. Contest economics — *the operator's decision; two additions*
The reviewer's table stands: at 0.9× the field's rate the system loses rake plus; minimum stake until three paper weeks
above break-even per contest type. Two additions:
- **Softness is measurable per contest before Sunday**, from the previous weeks' standings: the share of entries from
  20+-entry users and their mean percentile, by contest name. The 594-entry supersats had no heavy users; the FFWC is a
  professionals' contest. Publish it Friday with the ladders (`dk_contest_details.py` already runs then).
- **The $2 circle.** Three users in all 19 sat20s, ten regulars in 5–18 each. Against them our unique rows averaged 121.
  If the operator keeps them, S4's allocation is the only lever that does not need a better lineup.

### S10. DST — *class C; Week 5+*
Three of the five heaviest Week-3 exposures were DSTs that busted (Titans 7.0, Bengals 3.0, Seahawks 2.0 on 51/47/17
rows); DST is a constant in every incumbent world and a linear model with rank skill about 0.16; the 25% cap is the only
change. A market-anchored DST projection (opponent implied total and spread → points-allowed bands; sack and turnover
rates from nflverse; Kalshi's D/ST fantasy-point lines, which the R5 capture already snapshots) is cheap to fit
walk-forward on 2014–25 and would give the DST slot a distribution instead of a constant. Kill: no MAE/rank gain over
the current model on 2023–25.

### S11. Smaller items
- **T-70 vacated bump as a share, not a constant.** The +1.6/+0.7/+1.0 table is one census; the natural generalisation
  is a share of the out starter's projected volume (the review's own words), which scales with the starter. Test on the
  same replay census before Week 5.
- **Late swap guard.** L11: +11.1% aggregate, paired 30–32, and the Week-3 rehearsal cost the one real ticket. Until a
  paper week is scored, restrict swaps to rows whose simulated ticket gain exceeds a floor (e.g. +0.02 tickets), and
  log the counterfactual for every row not swapped.
- **The class sleeve's hard QB cap ($5,500)** is a three-week fashion; the Week-1 gate passed with it, so keep it, but
  print each week what share of the mean book came from the sleeve so a fashion turn shows up in the receipt.
- **Q10 from the post-mortem** (`GAME_SIM_PACE=vegas`; script-based cross-team coupling) is cheap and still untested; my
  09-25 card (§2.2–2.3 there) is the outcome-free gate for it.

---

## 4. What not to do
- **Don't re-run MAXGAME5 / QB+3** (L10: −1.6%, not eligible) or **the tilt** (L12 inconclusive) without a new predictor.
- **Don't fade ownership** (R2(a): the crowd's chased part is weakly informative against our projections).
- **Don't select the deep-line contests by the simulator's P(≥line)** (the reviewer is right about that form); S1 is a
  different estimate of the same quantity.
- **Don't add a fourth objective.** MEAN for p89–p96, a variance-aware or class-based rule for p98+, EMAX nowhere.
- **Don't trust a rehearsal number without its information set** (the tilt, the class pool map): the laptop's rule 2.

---

## 5. Sequencing (the operator decides)

| when | work | owner |
|---|---|---|
| Tue 09-29 | S3(1): the LineStar ownership pull (operator command) and the L05 reopening test on 2023–25 (LAG, LINESTAR, blend). S8: the written failure order | laptop; operator |
| Wed 09-30 | S5: the top-144-by-mean check in the full-size smoke; PMO rows into the Sunday pool if it fails. S2: the capture job for Saturday/T-70 public projections | laptop |
| Thu–Fri | S9: field softness by contest with the ladders. S3(2): `surprise_prev` in `ownership_sets.py`, walk-forward | laptop |
| after L13 reads | S1: PREREG-L14 (variance arms at p99) on L13's panel; S7: PREREG-L04b | laptop |
| Mon 10-05 | S6: class model v2 fit beside v1 in the Monday refit; S2's first graded week | laptop |
| Week 5+ | S10 DST model; S11 items | laptop |

Nothing above needs Cloud Run, a new job, or a change to the armed Week-4 configuration.

---

## Appendix: reproduction

`reports/lab-handoffs/2026-09-28-scoring-suggestions/` — four scripts that run on the panel built by the 09-25 scripts
(`fetch_public_inputs.py` then `c1_build_linestar_panel.py`, which write `ls_main.parquet` outside the repo):
`a_line_arithmetic.py` (§2.1), `b_ownership_predictors.py` (§2.2), `c_residual_sd_and_bias.py` (§2.3),
`d_calibration_replay.py` (§2.4; needs `pulp` and `scikit-learn`; about 15 minutes). Third-party data is never committed.
