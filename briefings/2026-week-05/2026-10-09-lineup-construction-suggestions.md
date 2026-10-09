# Lineup construction: what to try this weekend (2026-10-09, afternoon)

**For:** Erich, and the laptop agent who would build and test anything chosen here. Written by an outside model at your
request ("review the rules currently in place ... create a document of suggestions that we can try immediately for this
weekend"). Read for it: the ten Week-5 briefings, the study ledgers (production studies 1–91, lab cohorts 001–099), the
Week-5 arm and the lineup code as armed, the real-field analyses of Weeks 1–4, and the public record of how the pros
build (sources at the end). **Nothing here is a passed test.** Each suggestion names the test that has to pass before it
is armed, under your rules. Public file: no user names, no dollars.

## In one page

**Where the points go.** Five facts from this week's analyses explain most of the gap.

1. **Our lineups carry the highest projection in the field and score the lowest.** In your limited-entry contests of
   Weeks 1–4 (the 4444, 555, 333 and FFWC satellites), ours were projected 127–135 and scored 110–125; the top three
   finishers were projected 123–128 and scored 180–200 (HANDOFF, 10-09 13:12). In the Millionaire, the model rated our
   lineups above the average opponent's every week; in Weeks 2–4 they scored 4–13 points below (the calibration report).
   Fantasy Points' own numbers did the same on Week 4: our lineups +8.5 above the field's, scored 3.7 below.
2. **The cause is the way the solver uses the projection, not only the projection.** The book is 26 integer-program
   solves, each maximising the sum of Fantasy Points' projections (plus +2 for cheap players in 8 rows). That picks the
   players whose projection sits furthest above their price, which is exactly where projections are noisiest: our picking
   loss is concentrated at $6,000–7,999 (−6.0 points per lineup, three weeks of four), where every projection ranks
   players poorly (rank correlation 0.16–0.36). A hard optimiser on a noisy residual overpays for it. The pros tilt toward
   the market's favourites gently (about +1.6 points of exposure per standard deviation of edge); our solver tilts all the
   way.
3. **The expensive stars are missing.** The solver never buys the $8,000 receiver who is the 24th-best value: Lamb at
   $7,800 was in 0 of 26 rebuilt Week-4 rows; the top 3 of the $4,444 Showdown satellite all had him. The Millionaire's top
   1% hold about 0.9 players priced $8,000+ per lineup, the top finishers in your satellites "paid less at QB and DST and
   played more $8k+ studs"; your real book holds 0.54.
4. **Two tight ends in half the book.** The flex was a tight end in 14 of 26 rows (the top finishers 11–50%, the historical
   top-10 Milly lineups 9%). This one is already fixed for Sunday: study 91's row rule (one TE per row) went live today.
5. **Concentration, now bounded.** The W4 book put 97% of entries on 3 quarterbacks with an ownership sum of 152 against
   the field's 110. The armed package (35% player cap, each player at most 15 points above Fantasy Points' projected
   ownership) and the QB cap of 5 rows bound this; the row rule caps the sub-3%-owned players at one per row.

**What I recommend, in order.** Two construction ideas that have not been tested here and aim at facts 2 and 3, each
with the test that decides it today or tonight; then the smaller items.

| # | Change | Aims at | Test before arming | My recommendation |
|---|---|---|---|---|
| S1 | **Shrink the projection the solver sees toward the price**: each player's number = the slate's typical Fantasy Points projection at his salary and position + 0.7 × (his projection − that). The cheap block, caps and row rules are unchanged | Fact 2 | The outcome-blind Week-4 real-book check; a fifth book in tonight's Weeks 1–4 real-field replay; the harness if a lane is free | **Build and test today; arm Saturday only if it is not below the package on the real fields.** The strongest mechanism on the list |
| S2 | **One star per row**: every row holds at least one skill player priced $8,000 or more (as a stack mate, a bring-back or a one-off); an infeasible row is re-solved without it, as the row rules do | Fact 3 | The same two checks. The harness cannot measure it (its own books already hold a star in 18.5 of 26 rows); the real-field replay can | **Build and test today. Paper arm this week unless you want a second live change.** With the cheap block it is the "stars and scrubs" structure your satellites' winners showed |
| S3 | Sunday and Monday checks (section 4) | — | — | Do them |
| S4 | For Week 6: the running back as a stack mate; the defense paired with its own running back; dupe-aware dealing to one-seat satellites; ownership + 10 (study 90, tonight) | — | Harness + real-field | Queue |

**What I would not do this weekend.** Any forced-stack or forced-game rule, any price book, any QB-side rule, the
tight-end ban alone, late swap, a ceiling or finish-probability selector: every one has been tested here and read flat or
worse (section 5). Re-running them on the same slates is not new evidence.

**One caution on counting changes.** With the package and the row rules, Sunday already carries two new construction
changes plus the cheap block. Each one you add makes Monday less able to say which helped. S1 is the one I would add
live; S2 on paper beside it is free.

## 1. The diagnosis, in numbers

Everything in this table is from tracked reports; sources in brackets.

| Measure | Ours | Field / regulars | The winners | Source |
|---|---|---|---|---|
| Lineups: projected → scored, your limited-entry contests W1–4 | 127–135 → 110–125 | — | top 3: 123–128 → 180–200 | HANDOFF 10-09 13:12 |
| Model's rating of our lineups vs the average opponent, W2 / W3 / W4 (model → real) | +4.8 → −12.9; +2.9 → −11.7; +12.0 → −3.7 | — | — | calibration report |
| FP's rating, W4: our lineups vs the field's | +8.5 projected, −3.7 real | — | — | overnight sheet |
| Picking edge by salary tier, points per lineup | $6,000–7,999: **−6.0**; under $4,000: +2.0; DST +1.4 | regulars: +1.15 at $6–8k, +1.65 under $4k | — | where-our-picks-lose report |
| Players priced $8,000+ per lineup | 0.54 (your real book) | — | Milly top 1%: about 0.9 | leads log, lead 7 |
| Tight end in the flex | 14 of 26 rows (54%); 54–100% in your satellite entries | field 13% (2017–20); 35% (W4) | top-10 Milly lineups 9%; your satellites' top 3: 11–50% | ETR; W4 post-mortem; HANDOFF 13:12 |
| Players under 3% owned per lineup | about 1.0 | — | top 3 in your satellites: 0.4–0.5 | HANDOFF 13:12 |
| Ownership sum, W4 | 152 | 110 | top 10: 94; top 100: 99 | W4 post-mortem |
| Distinct QBs per 26 lineups; most-used QB's share of entries | 6–7; 51–59% | regulars cut to 26: 11; 23% | — | how-the-winners-spread; pre-mortem |
| Players over 40% of lineups | 9–10 | regulars cut to 26: 2 | — | how-the-winners-spread |
| Replacement for the most-used player: projected points vs him | −0.7 | regulars −3.2 (they accept a cheaper player and spend elsewhere) | — | how-the-winners-spread §2 |
| Stack mates with the QB (QB+2 or more) | 94% (W1–4); 45% under the winners' mix | field 30%; regulars 42% | top 1% 44% | outside review §1; pre-mortem |
| Bring-back | 97% (W1–4); 59% under the mix | field 43–47% | top 1% 59–62%; top 0.1% 66% | outside review; necessary-players |

**How to read it.** The field beats us at the player level by a few points per lineup, and the shortfall is largest
where our solver is most confident (the $6–8k tier, the top of the value ranking). The shape studies (sections 3 and 5)
mostly read "no difference" because shapes are not where the points are lost. The two levers below act on the picking
step itself, inside the construction you already run.

## 2. The baseline: what is armed for Sunday (so nothing here is double-counted)

From `scripts/arm_week5_saturday.sh` at FRIDAY_HEAD `f5f96468` and the HANDOFF entries of 10-09:

- **Projections:** Fantasy Points' DraftKings projection for every player FP covers (ours only as the fallback), captured
  at 10:40 and 10:46 CT, refused if older than 06:00 CT Sunday.
- **Shapes (the winners' mix, 26 rows):** 8 rows QB + 2 mates + a bring-back; 4 rows QB + 2 mates; 7 rows QB + 1 mate +
  a bring-back + a pair from a second game; 7 rows QB + 1 mate. A mate is a WR or TE on the QB's team (an RB does not
  count); a bring-back is an RB, WR or TE on the opponent. Cells are filled in round-robin turn. At most 4 players from
  one game; no RB against the lineup's own defense; no two RBs from one team.
- **The objective:** maximise the sum of projections. In 8 of the 26 rows (the cheap block) every non-DST player under
  $4,000 gets +2.
- **Caps:** no player in more than 9 rows (35%); each skill player at most 15 ownership points above FP's projected
  ownership (the ownership cap; falls back to the 50% book with an alert if the ownership file fails); no QB in more than
  5 rows; no defense in more than 6; every row differs from every earlier row by at least 5 players (overlap ≤ 4);
  salary $49,000–50,000.
- **Row rules (study 91, live today):** at most one TE per row; at most one player under 3% projected ownership per row.
- **Dealing:** the 26 super-satellite entries take rows 1–26, one each; the other contests open with the book's top rows
  (2, or 4 for contests over 5 entries) and fill with unique rows in your Rev6 priority order (4444 > 555 > WFFC > 333 >
  Millionaire > Warm Up). Rows are reused across contests, never within one.
- **On paper beside it (study 38):** today's book (0.5 cap, no ownership cap), the package without the row rules, the
  tight-end blocks, the matchup blocks, the regulars' tiers, and more.

## 3. The two suggestions, in full

### S1. Shrink the projection the solver sees toward the price (class C, calibration; new; recommended)

**What.** Before the rows are solved, replace each skill player's projection with:

    typical(salary, position) + 0.7 × (projection − typical(salary, position))

where `typical` is the slate's own curve of Fantasy Points projections against salary within the position (a smooth
median through the T-70 frame's FP numbers, so it is outcome-blind and available at build time). A player FP rates 4
points above his price keeps 2.8 of it; a player 2 below his price loses only 1.4 of the penalty. Defenses are left
alone. The cheap block's +2, the caps, the row rules and the shapes are unchanged. One parameter, `k = 0.7`; `k = 1`
is today's book exactly.

**Why this and why now.**
- It acts on the measured loss. Our picks lose at $6–8k because the solver takes the largest positive residuals, and in
  that tier the residuals are mostly noise (every projection's rank correlation with results there is 0.16–0.36; where
  our projection sat 1.5+ above the market the player fell 1.3 short; FP overrated our W4 rows by 12 points relative to
  the field). Shrinking the residual is the standard remedy for an optimiser that chases its own errors.
- It keeps FP as the base, which was your 10-05 decision, and it is not a blend: no second source is needed.
- It is how the pros' exposure actually behaves. Their tilt toward the market's favourites is proportional and mild
  (+1.6 points of exposure per standard deviation of edge; the ones who follow the market *harder* finish better on
  average, but none follows it all the way). The solver without shrinkage is the extreme case.
- It is reversible in one setting and visible in the receipt.

**What it costs.** The rows' FP-rated projection will fall, probably by 1–2 points per row; that is the point (the rated
number is the inflated one). The real cost is any true information in FP's residuals that the shrink discards: the
regulars earn about 1.9 points per lineup from following the market's residuals, so `k` should not go far below 0.7.

**Evidence against it, honestly.** No study here has tested it. The cheap block is itself a deliberate +2 residual and
has this season's field evidence behind it; S1 leaves it in place. Shrinkage will move the book toward more-owned
players; the ownership cap, the sub-3% row rule and the 35% cap still apply, so the book cannot collapse onto chalk.

**The test today.**
1. **Outcome-blind Week-4 real-book check** (the scripts in `reports/2026-10-09-option-w4-checks/`): rows changed, FP
   points per row, distinct players, stars per row, QBs, flex mix, ownership sum, at `k = 0.7` and `k = 0.5`.
2. **A fifth book in tonight's Weeks 1–4 real-field replay** (the laptop is already running today's book / the package /
   package + row rules / entered): add "package + row rules + shrink 0.7". Weeks 1–3 shrink our own projections the same
   way (the mechanism is identical); Week 4 shrinks FP's. Read P(≥ 1 big seat) per week and the mean entry percentile.
   Four in-sample weeks are a harm screen, not proof; say so in the record.
3. **If a harness lane is free overnight:** the same shrink on the lab's `player_mean`, 2023–24 deciding and 2022 as the
   check, two draws, your "better on both draws" rule.

**Arming.** A flag in `union_reselect` (`--proj-shrink-k`, default 1.0 = off; refuses values outside 0.5–1.0), set in the
arm script after the FP override and before the cheap block; FRIDAY_HEAD moves; the receipt records `k` and the curve's
sha; the Saturday 10:30 canary must show it. Rollback: unset the flag.

**Monday.** Study 38's TODAY and package arms already sit beside the live book on the real fields; the comparison is
automatic. Add the salary-tier picking line (the where-our-picks-lose report's table) to Monday's read so the $6–8k loss
is tracked week by week.

### S2. One star per row (class S, selection; new as a rule; paper this week unless you choose otherwise)

**What.** Every row holds at least one non-QB skill player priced $8,000 or more. He may be a stack mate, the bring-back
or a one-off. A row that cannot be solved with the constraint is re-solved without it and recorded, exactly as study
91's row rules behave. The 9-row player cap and the ownership cap still bound how often any one star appears.

**Why.**
- The solver's value logic never buys the expensive receiver. On Week 4's slate Lamb ($7,800) was the 24th-best value and
  appeared in 0 of 26 rebuilt rows; the top 3 of the $4,444 Showdown satellite (380 entries, one seat) all had him. A flat
  bonus to top receivers did not fix it (0 of 26 at +2, +3 and +4); only a constraint can.
- The top finishers in your limited-entry contests "paid less at QB and DST and played more $8k+ studs"; the Millionaire's
  top 1% hold about 0.9 such players per lineup against your 0.54; the Week-4 top 10 spent $20,050 on three receivers
  against the field's $18,083.
- With the cheap block (two or more sub-$4,000 players in 8 rows) this is the barbell the winners show: cheap volume
  plays paying for a star, instead of the middle tier where our picks lose.
- Removing stars is clearly bad in the harness (study 86, no player over $7,900: −4.9, 18% fewer expected big seats), and
  a one-star rule leaned positive in every season in study 78's side arm. Neither proves that forcing a star helps; they
  say the direction is not wrong.

**Evidence against it, honestly.** Study 78's two-star version failed a guard; the one-star arm barely bound in the
harness because the harness's books already hold a star in 18.5 of 26 rows, so the harness cannot read this rule. Stars
helped in Weeks 1–3 and hurt in Week 4. The rule binds hard on your real book (11 → up to 26 rows), so its cost there is
unknown until checked.

**The test today.** The same Week-4 real-book check (rows changed, FP per row, which stars, how many rows per star) and the
same fifth-book slot in the real-field replay ("package + row rules + star"). If both S1 and S2 are built, run the pair
as a seventh book too.

**Arming, if you choose it live.** A third row rule (`star1`) in the vehicle study 91 built (`row_rule_sets`), so parity
with the lab's paper arm is the same mechanism; FRIDAY_HEAD moves; study 38 gets an amendment so its paper arms follow.
Otherwise a paper arm in study 38 for Week 5 and the decision for Week 6 on real results.

### S3. Smaller construction items for Week 6 (not this weekend)

- **The running back as a stack mate.** Today a mate is a WR or TE only. The Week-2 2026 Millionaire was won with QB +
  RB + TE from one team; pass-catching backs correlate with their QB. Allowing an RB to count as one of the two mates
  adds a shape the book cannot build today. Needs a lab code change (the stack definition), so a harness study first.
- **The defense with its own running back.** Positive game-script correlation (a leading team runs and its defense gets
  sacks and turnovers); the Week-3 2025 winner paired Mason with the Vikings' defense. Untested here. A small bonus in a
  few rows, harness first.
- **Dupe-aware dealing** (study-list row 50, approved for Week 6): send the rows with the lowest ownership product to the
  one-seat satellites, where a tie halves or loses the seat. Copies are observable every Monday.
- **Ownership + 10 instead of + 15** (study 90, running tonight as a Week-6 candidate).

## 4. Sunday and Monday: what to check, no decision needed

- **The 10:30 canary's receipt** must show: cap share 0.35, the ownership cap applied with its source, row rules
  `te1_low1`, the cheap block's sha and 8 rows, FP as the projection source with its update time, and (if armed) the
  shrink `k`.
- **This slate.** Eleven games (Kansas City and Carolina on bye); eight at 1 p.m. ET and the rest late. Detroit–Arizona
  is the highest total at 54.5, nine points clear of the next game, and it is in the late window; Detroit has the highest
  implied total on the board. FP's projected ownership will pile into that game. Expect the ownership cap to bind on
  Lions and Cardinals, and count in the book how many rows and QBs it leaves there: the top-total game is the week's
  highest-scoring game only 16–19% of the time, and Weeks 1, 3 and 4 were won by a favourite QB from the second- or
  third-highest total.
- **Monday, in this order:** the real-field report per contest (study 38's scorer places the paper books and the entered
  book in the real fields); the calibration check re-centred on FP (planned on 10-09); the FP-vs-props line; the
  salary-tier picking line (new, above); the cheap block's first stop-rule read is 10-19.

## 5. Tested here and not worth re-running on the same slates

Numbers are percentage points of the chance of at least one big seat per slate, 2023–24 deciding, from the ledgers.

- **Forced stacks and forced games:** a stack in every top game (43: −2.8); the opponent's top receiver as the bring-back
  (71: −1.9; 71b: −1.4); QB + top catcher in the top games (73: −3.6); the full game trio (74: −2.9); two bring-backs
  (76: −1.4); a shootout whole book (26: flat).
- **Which QB:** the underdog's or the favourite's from a top game (80: −0.4 / −3.8); the lower-implied half (82: flat);
  a cheaper QB (88: −4.8); every QB his best row (47: −5.1); a per-game QB cap (24: cost 22% of seats).
- **Price books:** TE ≤ $5k + DST ≤ $3k + a cheap WR + no TE flex (85: −3.1; 87's price part −6.1); no player over
  $7,900 (86: −4.9); the tight-end ban alone (81 +4.7, 84 −1.2: bank-set noise).
- **Selection and sorting:** ceiling / p90 / quantile selectors (five times, negative); finish-probability and sim-ROI
  selection against a simulated field (PREREG-098, negative); winner-likeness scores (48–48e, no support on real fields);
  every one-row ranking trails random (32); deals by touchdowns, priority or winner score (52, 59, 48b: no difference).
- **Late swap:** the chase policy (lab 023: −1.23 on the weekly max) and fresh tickets for hopeless rows (024: −0.42),
  building for optionality (L22: harmful). Closed under the lab's information set; a real-field paper version is the
  only honest reopening and is not a weekend item.
- **Concentration caps alone:** the 35% cap without the ownership cap (89: −2.0 on both draws); a per-player entry cap
  (1b); de-concentration by game (1).
- **The ownership term under FP:** removed for Week 5 by your decision after studies 29–31 and the FP check (at the same
  FP projection, higher-owned players scored slightly less: −1.2 per 10 points, not different from zero).
- **A projection blend:** your decision was FP alone; the frozen weekly FP-vs-blend check runs from Week 5. S1 is not a
  blend.

## 6. How the pros build, for reference

**The historical Milly Maker top-10s (452 lineups, 2017–2020, Establish The Run):** QB + 2 teammates 41% vs the field
29% (the clearest edge); naked QB 6% vs 17%; one bring-back 36% vs 31%; TE in the flex 9% vs 13%, RB in the flex 58% vs
52%; full salary used 48% vs 42%; a sub-$6k QB 45% vs 38%; RB at $6.5k+ 49% vs 43%; cumulative ownership averaging 116%
with 89% under 150%; 2.3 players under 5% owned and 1.9 at 20%+ per lineup.

**The 2026 Millionaire so far:** Week 1 won at 273.98 with three running backs (one in the flex) and a late-window QB +
WR pair, no bring-back; Week 2 at 232.38 with a 49ers QB + RB + TE stack, two tight ends, a 0.7%-owned receiver, no
bring-back; Week 4 at 234.2 with a Cowboys–Texans stack (Prescott 5.2% owned, Lamb 44.3 points, Collins, Hockenson).
Winning scores run 229–240 on average; "to post above 200 a roster needs at least three players over 30".

**The 117 regulars (150 lineups every week, W1–4):** QB + 2 42%, QB + 1 51%, bring-back 46%, 5.1 games per lineup,
$165 salary left, ownership sum 103, 5% of lineups duplicated; 16.9 distinct QBs per 147 entries (top QB 23%), the
most-used player 53%. Their edge is about 4 points per lineup: half from following a market-anchored projection more
closely than the crowd, half beyond the market at TE and QB. The habits beyond the projection (selling last week's
scorers and salary risers, ignoring 1–3-game matchup stats, buying steady routes, lightly fading the crowd) are leverage,
not information.

**Their tools:** a sampled pool, a contest simulation against a projected field, one sort number per lineup (simulated
ROI or a risk-adjusted version), a minimum of 3–4 differing players between chosen lineups, and filters on ownership
product (duplication), stack type and salary left. The simulation half of that pipeline has been tried here and lost
because our simulator's tails are not good enough; the filters are the part this book already runs (overlap 4, caps).

## 7. Sources

Repository: `briefings/2026-week-05/*` (the calibration report, the overnight decision sheet, the promising-leads log, how
the winners spread, the necessary players, how the pros pick players, the pre-mortem); `reports/2026-10-07-where-our-picks-lose-by-salary-tier.md`;
`reports/2026-10-07-why-we-missed-the-winners-players.md`; `reports/2026-10-07-how-professionals-sort-lineups.md`;
`reports/2026-10-07-week5-options-this-week.md`; `reports/2026-10-05-max-entry-regulars.md`;
`reports/2026-10-06-outside-review-suggestions-for-high-scoring-lineups.md`; `reports/2026-07-25-system-study.md`
Addenda 122–188; the lab ledger at `fd42c679` (studies 24–91) and `LEDGER.md` rows 003–097; `HANDOFF.md` entries of
2026-10-09; `scripts/arm_week5_saturday.sh`, `scripts/union_reselect.py`, `src/nfl_dfs/inference/mix_shapes.py`,
`src/nfl_dfs/inference/enter_layout.py`.

Web (read 2026-10-09):
- Establish The Run, "Levitan: Winning DraftKings Milly Maker Trends" (2020-10-26; 452 top-10 lineups, 2017–2020):
  https://establishtherun.com/levitan-winning-draftkings-milly-maker-trends/
- DraftKings Network, Millionaire winning lineups 2026 Week 1, Week 2 and Week 4:
  https://dknetwork.draftkings.com/2026/09/14/draftkings-nfl-millionaire-winning-lineup-week-1/ ,
  https://dknetwork.draftkings.com/2026/09/21/draftkings-nfl-millionaire-winning-lineup-week-2/ ,
  https://dknetwork.draftkings.com/2026/10/05/draftkings-nfl-millionaire-winning-lineup-week-4/
- Sports Illustrated, "DraftKings Millionaire Maker: winning stacks and lessons from past champions":
  https://www.si.com/onsi/fantasy/dfs/draftkings-millionaire-maker-winning-dfs-stacks-lessons-past-champions
- Stokastic, "Milly Maker DFS strategy" and "NFL DFS late swap":
  https://www.stokastic.com/articles/dfs-strategy/milly-maker-dfs-strategy ,
  https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-late-swap
- FantasyLabs, Week 5 2026 main-slate look-ahead and leverage picks:
  https://www.fantasylabs.com/articles/nfl-dfs-week-5-draftkings-main-slate-look-ahead-early-values-in-our-projections-2026/ ,
  https://www.fantasylabs.com/articles/nfl-dfs-leverage-picks-on-draftkings-for-week-5-2026/
- ESPN, Week 5 2026 odds and totals:
  https://www.espn.com/espn/betting/story/_/id/50085464/2026-nfl-week-5-schedule-odds-betting-point-spreads-totals
