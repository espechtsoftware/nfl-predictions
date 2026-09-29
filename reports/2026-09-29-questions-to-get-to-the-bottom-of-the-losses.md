# Questions to get to the bottom of where the points and the money go (2026-09-29)

Written for the operator, to put to the laptop agent, the reviewer and production. Each question says what is already
known, so it is not asked twice, and what a good answer has to contain. Production compiled it from the winner
analyses (settlement reports, the three post-mortems, the winner-anatomy and B1 census reports, the 09-22 review), the
lab ledger through L18, and the untested-ideas lists (outside-the-box review, unturned-stones audit, the Week-2 and
Week-3 proposal lists). No dollar figures; the stake plan stays private.

## The picture the evidence already paints

1. **Our lineups average below the field.** Week 1 the pool mean sat at the field's 49th percentile, Week 2 the 22nd,
   Week 3 our Millionaire entry was exactly the median. Winners (down to the 1,000th place) are chalkier than the
   field, spend on stud RB/WR, take a cheap stacked QB and a cheap TE (often two TEs), and lean on late games.
2. **The Millionaire cannot be won from any pool we have built.** 0 of 68 historical winners beaten, 0 of 3 in 2026;
   pool ceiling 30–40 points short; P(win) 0.0% even with +40 points on every row. The top-100 line (208–245) is
   above the pool's best in every 2026 week.
3. **The money is in contests that pay the average lineup**, and every tested selector sits at 0.8–0.9× the field
   mean where break-even after rake needs 1.10–1.19×. Lifetime ROI is negative in every contest class.
4. **The projections are "as accurate as the market"**, yet the book is worse than the field average. So the loss is
   between projection and entry: valuation (p90 punts, backups valued at 10+), generation (mandated QB+2+bring-back,
   3.7 games per row), selection (expected-max drifted away from chalk; mean selection is +23–31 per row live), and
   timing (Saturday information; Sunday news like Sadiq).
5. **The field's chalk is a good forecaster at the top** (Gibbs, Wilson, JSN hit; our over-weights busted), excess
   ownership predicts the residual (ρ +0.17), and winners are a chalk core plus 3–5 leverage pieces — a shape 7% of
   our Week-2 pool had.
6. **Persistence is real but modest:** users with 20+ entries in both Week 1 and Week 2 carry a Spearman +0.116
   week-to-week finish correlation; the persistent ones are chalkier with fewer sub-5% players; their stacking is
   identical to everyone else's. The full portfolio/persistence study (Q11) is due Wednesday.
7. **The simulator's slate level is off** (mean ≈123 every week vs realized 141 and 94), it over-predicts P(≥200)
   about 3×, and the tail sleeve it drives chose 110–137-point rows in Week 3.

## A. Money first: what am I paying for, and which contests can our quality actually beat?

A1. **For every contest class I enter, what multiple of the field's mean lineup does break-even require after rake,
    and where does our current book sit?** Known: 1.10–1.19× needed; MEAN book ≈0.9×, EMAX ≈0.8× (production
    "what winning requires", 09-22). Ask for the same table per class (Millionaire, FFWC qualifier, $4,444 sats,
    wildcats, 20-max supersats, 11-entry satellites) using the Week 1–3 fields and the Week-4 book form.
A2. **Which contests have a positive expected return at our measured quality, and what is the weekly expectation
    if I enter only those?** A good answer is a table: contest class, entries, P(cash), P(ticket), EV per entry.
A3. **What is a Millionaire seat actually worth to us?** Not P(win) (0.0%) but the whole finish distribution of one
    seat from our book: P(top 1,000), P(top 100), expected payout. If it is a lottery ticket, say so and size it.
A4. **Why is `payout` NULL on every contest_entries row, and when will ROI per contest be computable?** Without it
    the contest-mix question (Q9) is guesswork.
A5. **Is there a satellite/qualifier where volume does NOT beat single entries (per-entry rate flat in 5-max and
    20-max fields)?** Those are the contests where our process, not our entry count, decides; concentrate there?

## B. The funnel: where between projection and entry do the points go?

B1. **Per 2026 week, per stage, what is the mean lineup score at: (1) the best lineup our projections can build,
    (2) the pool by batch (lev / boom / class sleeve / PMO), (3) the entered book, (4) the field, (5) the field's
    top 1%?** One table per week. The stage with the biggest drop is the lever. Known pieces: Week 3 pool 12.2% above
    cash vs book 10.4%; lev rows mean 137 vs boom 116; top-mean 151 vs entered 120.
B2. **How many of our entered rows carried a predictable dud** (a player who scored under 5 and was Out/Doubtful,
    a backup, a sub-1-point projection, or a p90-valued punt at 2.3 projection)? Known: 399 boom lineups held a
    sub-1-point player in Week 3; 7.4% of $4k-and-under players score 10+. Ask for the points lost per row to this
    class alone, each week.
B3. **Is the p90 punt valuation earning its keep under the MEAN objective?** It was kept because "true-deletion
    tests cost tails" on the old best-of-40 objective. Q4b (p90 vs plain mean for the leverage batch) has no read.
B4. **Where does our salary go versus the winners, and is that a projection bias by position and price tier?**
    Known: Week 3 we overpaid QB +$840, TE +$465, DST +$160 and underpaid WR −$1,317, RB −$688 vs the top 100. Ask
    for points-per-dollar calibration by position × salary tier on 2023–25 and 2026: do we over-project expensive
    QBs/TEs and under-project stud WRs?
B5. **Does the mandated QB+2 + bring-back in EVERY row cost mean points?** Field top 1% has two-deep stacks in ~30%
    and bring-backs in ~41%; we are at 100%/100% and 3.7 distinct games per row vs 5.4. Stack depth was closed on the
    TAIL objective; has anyone measured the mandate on the MEAN track and on tickets at the satellite lines?
B6. **What does a "dumb baseline" book score?** The book you get by optimizing consensus projections (LineStar/ETR/
    a free optimizer) with default rules and no simulator, top-K by projection, scored on Weeks 1–3 and the
    36-slate panel. If we cannot beat that, every sophisticated stage is a net cost. This baseline does not exist.

## C. The field as a forecaster: are we using ownership the right way round?

C1. **Head to head, across 74 historical slates and the 3 live weeks: the field's top-10 most-owned players versus
    our top-10 projected (same position), realized points.** Who forecasts better at the top? Known fragments: the
    chalk hit in Week 3; ownership vs points +0.26 in Week 2; excess ownership predicts the residual (+0.17).
C2. **What is the "field-implied projection"** (invert pre-lock ownership to a projection via salary and slot), and
    does blending it into our served projection cut MAE and raise the mean-track score? This is ownership as a
    projection input, not a fade or a tilt (L12 tilt was inconclusive; the fade never fired in 2026).
C3. **Which pre-lock ownership source is closest to the realized field, at what hour?** LineStar projected
    ownership (captured Saturday and T-70 from Week 4), our lag model, our booster. Known: the LAG+LineStar blend's
    top-15 overlap 9.2–9.8 vs lag 5.3–6.7. Ask for the realized top-15 hit rate by source and by capture time.
C4. **What share of our pool, and of our entered book, has the winners' shape (chalk core: ≤2 players under 5%,
    ≥1 at 20%+), and how do those rows score versus the rest?** Known: 7.2% of the Week-2 pool; chalk-core selection
    lifted Week 1. Should the generator produce that shape on purpose (L07 tests one form of it)?
C5. **Duplication: how many of our entered lineups are duplicated in the field, how many of the winners' are, and
    what is the cost of a duplicate at each line?** Never measured for 2026 (R12 untested).

## D. Information timing: how much of the gap is Sunday news?

D1. **Per week, how many points did Sunday-morning information add to the best available book** (T-70 rebuild vs
    Saturday, same selector), and which players moved? Known: Week 2 +7.7, Week 3 row 1 142 vs 128; Sadiq in 21 of
    the top 25 was Sunday news. Separate the news effect from the dose effect.
D2. **After the T-70 build, what information still arrives before the late games** (inactives at 11:30, weather,
    line moves), and is any of it exploitable on the MEAN track (L11 tested a tail form only, not supported)?
D3. **Are the availability repairs complete?** Backups valued at E[points | played], Doubtful exclusion, Q haircut
    over-discounting cleared players by ~11%: what is the residual points lost to availability per week now?

## E. The simulator: what is it still buying us?

E1. **If the simulator were removed from the money path, what would change?** The mean track selects by projected
    sum; the PMO main solves on simulated means (which equal the projections?); only the tail sleeve and the P(≥line)
    tools use the worlds. Ask for a precise list of decisions the simulator still makes and their measured value.
E2. **Is the slate LEVEL calibrated week to week** (sim mean 123 vs realized 141 / 94), and can the level be pinned
    to the market total the way the pace question (Q10, never run) proposed?
E3. **Are player tails calibrated?** P(≥200) over-predicted 3×; lev rosters 2.8× over; deep-world optima carry
    "never-realized" spikes (+19 points of excess). Which single fix (tail cap, world reweighting) has a preregistered
    test, and why is PREREG-101 withdrawn?
E4. **Cross-team correlation:** realized +0.21 vs ~0 simulated; WR1–WR2 +0.016 real vs +0.277 in the law. Does the
    dependence card (R8) change anything on the MEAN track, or only the tail?

## F. Portfolios, volume and persistence (the Q11 study, and beyond it)

F1. **Do top finishers persist?** Known: Spearman +0.116 (Weeks 1→2, 721 users with 20+ entries). Ask for all three
    weeks, for top-100 and top-10 users by name, and whether their EDGE is players (yes so far) or shapes (no).
F2. **What do persistent winners' portfolios look like** (exposure concentration, number of cores, which slots vary,
    QB count, uniqueness, average score, cash share)? Known first look: 150-entry top-10 users put 60–73% of rows on
    3–4 players and average 138–152 with 32–47% above the cash line; small-entry winners build 3–5 rows on one core.
F3. **Can we emulate that shape from our own pool and land in their class of average score?** If yes, the remaining
    gap is projection edge; if no, shape is not the explanation. (Q11 part 3.)
F4. **Per-entry ROI by entry count in each contest class** (150-entry users lift 1.88 in the Millionaire top 1%, flat
    in 20-max). Which of my contests reward process, which reward volume?
F5. **Which players decided each winning lineup** (one 40-point boom or five 25-point games), and were those players
    in our pool, in our book, and at what exposure? Known: 3.4 players at 30+ per historical winner vs our 1.8; the
    WR slot is the largest deficit (29.9 vs 19.9). Never decomposed per winner.

## G. The research process: are we closing doors on the wrong objective?

G1. **Which "closed" verdicts were closed on the old objective** (best-of-40 above 194, or the share of a simulated
    field above the book's best) **and should be re-read under the mean track and satellite tickets?** Candidates:
    late swap, exposure caps, stack mandates, punt valuation, the market blend weight (L04), the all-boom pool (L01).
G2. **What effect size can three live weeks detect, and what is the in-season adoption rule?** Several Week-4 changes
    (union, PMO main, DST cap, sleeve source) were entered on one-week rehearsals; the class selector was withdrawn on
    one out-of-sample week. Ask for a stated rule so adoptions and withdrawals are symmetric.
G3. **Are the 36 historical slates representative of 2026?** Same slates reused for L09–L19; DK pricing and the field
    change yearly; the 2021 FLEX field was more contrarian than 2026's. Ask for per-season stability of every
    verdict that drives Week 4.
G4. **What is the noise floor of the panel reads** (paired records 17–20, 21–25 with 35 ties), and how many of the
    SUPPORTED/HARMFUL calls would flip on fresh banks? L17's control replicated exactly (331 twice); ask the same of
    the levers that were adopted.
G5. **What was proposed and never tested, ranked by expected value per hour?** The lists exist (outside-the-box R3–R9,
    the Week-2 class-C proposals, Q10 pace, Q4b punts, orphaned preregs 051/061/062/072/075/077, ETR as an input,
    weather). Ask for a ranked queue with the reason each was skipped.

## H. Data we are missing

H1. **Historical field lineups**: contest_entries holds 2026 only; the 2021 RTS clone has 74 contests. Can more be
    bought or scraped, so persistence and duplication can be studied on more than three weeks?
H2. **Payout tables** per contest (R13): needed for A1–A4.
H3. **Pre-lock ownership with a timestamp** (LineStar captures from Week 4): the provable-pre-lock condition the
    reviewer set for L07's live use.
H4. **A mid-slate standings export**, if DK allows one, so late-swap behaviour of winners becomes measurable (never
    verified).

## Three questions to ask first

1. B6 — the dumb-baseline book. If a free consensus-projection optimizer beats our book on the mean track, the whole
   program is answering the wrong question and the fix is cheap.
2. A2 — the contest classes where our measured quality clears the rake. That is the one decision that changes the
   weekly result immediately, and it needs H2 (payouts) to be exact.
3. B1 — the per-stage funnel on each 2026 week. It turns "we lose" into "we lose HERE", which is what every other
   question refines.
