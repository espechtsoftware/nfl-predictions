# The promising-leads log (started 2026-10-09)

**For:** Erich. Your request (10-09): *"Please make a note of the TE findings that are somewhat promising. For each item that
seems promising at all, let's log it and after we're done, we can consider versions with them."* Kept by the outside
reviewer and updated as each study is read.

## How to read this log

- **"Points"** are percentage points of the chance of at least one big win, per slate, on the test model (the harness) —
  for example +2.0 means about 2 more slates in 100 with a big win. The main read is 2023–24; 2022 is the separate check.
- **This morning's caution (study 84):** the test model's results move a lot between random draws. The *identical* rule
  ("no TE priced $5,000 or more in any lineup") read **+4.7** on one draw and **−1.2** on another. So **a lean of a few
  points, either way, is within the noise.** Nothing below is a proven gain.
- **The rule from now on:** before acting on any lead, re-read it on a fresh, independent draw. Only a lead that holds
  up twice counts.
- **"Real book"** = what the rule does to your actual Week-4 book, built with Week 4's inputs and today's settings (no scores used).

## Tight-end leads

### 1. No tight end priced $5,000 or more in any lineup — *mixed; the most-tested lead*
| Reading | Result (2023–24) | 2022 |
|---|---|---|
| Study 81 (as its side reading) | **+4.7** (2023 +3.2, 2024 +6.2); about 10% more expected big wins | +1.7 |
| Study 84, TE ban alone (a fresh draw) | **−1.2** (2023 −0.9, 2024 −1.5); 15% fewer expected big wins | +2.9 |
| Study 85, "TE ≤ $5,000" ($5,000 itself allowed) | **+0.8** (2023 +0.7, 2024 +1.0) | +1.3 |
- **Real book:** changes 24 of 26 lineups; costs **0.76** projected points per lineup; TE in the flex 14 → 7; QB + own-TE
  stacks 12 → 10.
- **Average of the three reads: about +1.4.** Not proven, and costly to your real book.
- **Versions to consider later:** a lighter dose (e.g. at most 3 lineups with a $5k+ TE, the winners' rate); only the
  highest-priced TE banned; a paper test on real weeks.

### 2. No $5k+ tight end PLUS a receiver in the flex (3 lineups) — *the best single reading this morning*
- **Study 84 (TE_FLEX): +3.3** (2023 +5.0, 2024 +1.5); **2022 +6.2**; expected big wins unchanged (×1.00).
- **Read only once**, and it was the best of six versions in that run (a best-of-six pick flatters itself).
- **Versions to consider later:** re-read it on a fresh draw first; a receiver in the flex without the TE ban is lead 3.

### 3. A wide receiver in the flex — *leaned positive, failed its 2022 check*
- **Study 75 (8 lineups): +2.3** (2023 +1.6, 2024 +3.0); about 7% more expected big wins; **2022 −1.1**.
- **Real book:** 8 lineups → flex WR / TE / RB 1/14/11 → 8/9/9 (the receivers mostly replace tight ends); a 3-lineup
  version → 4/11/11 at −0.31 projected points per lineup.
- **Related, flat:** "no tight end in the flex" (study 85) +0.2; 2022 +3.4.
- **Versions to consider later:** 3 or 4 lineups; with lead 2's TE ban; a paper test on real weeks.
- **Re-read on your armed Week-5 version (study 93, 8 lineups): −0.3** (opponent set A −0.9, set B +0.3) — flat. Paper only.

### 4. A small bonus for tight ends in 8 lineups — *slightly positive, all three tested forms*
- **Study 63:** pass-catching TEs +2 → **+1.3** (2022 +2.5); against the toughest pass defences → **+1.9** (2022 +1.1); cheap
  OR pass-catching TE → **+1.2** (2022 +1.8). Each "no difference", each not contradicted.
- **Forcing QB + tight-end stacks** (same study) leaned the other way: −1.6.
- **Already running on paper:** these three blocks are paper versions in the weekly paper comparison from Week 5 (no money).

## Other leads

### 5. The QB alone in 3 lineups (study 77) — *small, positive in every season*
- **+1.8** (2023 +1.4, 2024 +2.3); 2022 +0.2; about 4% more expected big wins.
- **Real book:** 3 lineups at positions 3 / 7 / 13; +0.11 projected points per lineup.
- **In combinations it did not hold:** with the one-catcher and flex rules (study 83) −1.9; the same on another draw (84)
  +1.0; with the TE ban (84) −2.0.
- **Versions to consider later:** alone, re-read on a fresh draw; 6 lineups (+1.8 on its first read).
- **Re-read on your armed Week-5 version (study 93): −0.2** (opponent set A +1.4, set B −1.8) — flat. Paper only.

### 6. One receiver per team, all of the QB + 1 lineups (study 79) — *ARMED for Week 5 (your decision; every check passed)*
- **8-lineup version +2.0** (2023 +0.2, 2024 +3.8), 2022 +1.3 — but it changes nothing in your real book.
- **The every-lineup version +2.1**, 2022 +0.8 (a side reading). **Real book:** removes 6 of your 7 same-team receiver pairs
  away from the QB; 8 lineups change; no projection cost (+0.03).
- **With the TE ban (84): +0.3.**
- **Versions to consider later:** the every-lineup version alone, re-read on a fresh draw.
- **Re-read on your armed Week-5 version (study 93; 36 past slates, two random opponent sets): +2.0** (set A +3.6, set B +0.5);
  about 11% more expected big wins — it passed your "better on both draws" rule, the only one of study 93's three to do so.
  Under no true effect a rule passes about one time in four to one in three.
- **Your decision (10-09): "Live W5 if built in time".** Built and tested tonight (production flag `--mix-one-catcher-all`; it
  matches the tested rule line for line, including the cheap-block lineups). It goes live at Saturday's arming only if the
  Week-4 check and the paper-arm check pass; your armed book without it is scored on paper beside it. Otherwise it goes to paper.
- **Both checks passed on 10-09:** on your real Week-4 book the rule removed all 5 same-team receiver pairs away from the QB
  (19 of 26 lineups change; −0.06 projected points per lineup), and the paper arms follow it, with the book without it
  scored beside it. It is armed for Saturday.

### 7. At least one star ($8,000+) in each of the first 8 lineups (study 78) — *positive in every season, but barely tested*
- **+2.1** (2023 +1.5, 2024 +2.7), 2022 +1.0 — a side reading; the test model's book already had a star in most of those
  lineups, so it changed little there.
- **Your real book** holds about half a star per lineup (0.54; the 2026 Week 1–4 Millionaires' top 1% about 0.9 — the outside
  reviewer's scan for study 78), so the rule would change much more there.
- **Versions to consider later:** a real-book check first, then a paper test. (Two stars per lineup was mixed: off.)

### 8. Limit how far above the field we go on any player (study 89) — *the first lever today that points the right way on both draws; ARMED for Week 5*
- **Why:** in Weeks 2–4 the players we held far above the field fell short, and the ones we held below it did better
  (the outside reviewer's breakdown of your real entries, 10-09).
- **Study 89 (two separate draws):** 35% max + each player capped at the field's projected ownership + 15 points: **+1.2**
  vs your book (draw A +0.5, draw B +1.9); about 5% fewer expected big wins; within the noise. The ownership cap on top of
  the 35% max alone: **+3.2** (both draws positive). With the field's *actual* ownership (a best case): +2.5.
- **The 35% max alone: −2.0** (both draws negative) — by your rule it is NOT armed on its own.
- **Your decision (10-09):** a live Week-5 trial if built and checked in time — **it was, and you said "Yes, arm the
  package"**: 35% max + each skill player at most Fantasy Points' projected ownership + 15 points; today's book (50%, no
  ownership cap) is scored on paper beside it; if Sunday's ownership file fails, the book falls back to today's book.
- **On your Week-4 book:** no player in more than 9 of 26 lineups (was 13), players in 40%+ of lineups 7 → 0, distinct
  players 48 → 54, about 2.9 projected points per lineup lower.

### 9. At most one TE and at most one very-low-owned player per lineup (study 91) — *LIVE in Week 5 (your decision)*
- **Study 91 (36 past slates, two random opponent sets), on top of your package:** both rules **+4.1** (A +3.2, B +5.0), 8% more
  expected big wins — passed your "better on both draws" rule. The low-ownership half alone +2.8 (a clean pass); the TE half
  alone +0.9 (flat, a third time).
- **On your real book** the low-ownership half rarely triggers (Fantasy Points' projections and ownership agree), so live it acts
  mostly as "no TE in the flex". **Week-4 real-contest replay:** the armed version finished best (59th percentile, 20 top-10%,
  6 cashes, 0.57× vs the package's 55th / 13 / 3 / 0.29×) — partly hindsight.
- Your package without these rules is scored on paper beside it.

### 10. Ownership + 10 instead of + 15 (study 90) — *a tie; kept + 15 (your decision)*
- +0.8 (A +0.9, B +0.6), 3% fewer expected big wins; costs 0.9 more projected points per lineup on your real book.
- A second reading of the package against your old 50% book: +0.3 (the first read was +1.2) — roughly even in the test model.

### 11. The QB's own running back as a stack mate, 4 lineups (studies 94, 96) — *did not hold up on top of one receiver per team: paper only*
- **Study 94 (36 past slates, two random opponent sets), on your armed version:** in the first 4 QB-plus-one lineups, the QB,
  one of his receivers and his own running back. **+2.0** (set A +1.7, set B +2.4); about 3% more expected big wins. It passed
  your "better on both draws" rule. Under no true effect a rule passes about one time in four to one in three, and two of the
  five leads read tonight passed (this and one receiver per team), which is about what chance gives.
- **Where the gain came from:** all from the 2023 slates (+4.4); 2024 was −0.4.
- **Real book (Week 4):** 3 of the first 4 QB-plus-one lineups change.
- **Not yet read on top of one receiver per team.** That rule is armed for Week 5, so this one needs its own read on top of it
  before it can go live.
- **Your decision (10-09): "Try live W5 if built".** Tonight: a test of it together with one receiver per team (study 96, your
  rule), the production switch, the Week-4 check and the paper-arm check. It goes live at Saturday's 10:28 arming only if all
  pass; otherwise it goes to paper. It would be the fourth change this week.
- **Study 96 (the test together with one receiver per team, tonight): −0.5** (set A −0.7, set B −0.2); about 3% fewer
  expected big wins. It failed your rule on both random opponent sets, although the rule bound in every case (the QB's own
  back was in all 4 lineups each time). So study 94's +2.0 did not hold up once one receiver per team is in. It stays on
  paper (scored on the real Week-5 fields beside your book); the switch stays off. The game-script versions (the back only
  on an expected winner, or a winner in a high-scoring game) are study 97, tonight.

### 12. Your shape mix (studies 95, 98) — *it holds up; keep 30 / 14 / 28 / 28*
- **Study 95 (36 past slates, two random opponent sets), on your armed book:** removing A1 (−2.0), B (−2.5) or C (−1.2) made
  the book worse on both opponent sets; removing A2 changed nothing (+0.1). A book of only B (−4.5) or only C (−3.7) was
  worse on both sets (not separable from zero); only A1 (−0.5) or only A2 (+1.0) was mixed. No version passed your rule.
- **The rule written before the run** turns that into: A1 39% / A2 12% / B 24% / C 24% (two more A1 lineups, one fewer A2 and
  C), because removing A1 hurt on both sets while A1 alone did not. The reading behind it is weak (−2.0, interval −6.9 to +2.8),
  and the new mix itself was not tested — keeping the live mix is just as defensible. Your call in the morning (one setting).
- **Study 98 tested that suggested mix on a fresh set of simulated opponents: +0.6, a coin flip** (one set flat at −0.0,
  the other +1.1). It failed your rule. So nothing tonight says to change your shape mix: keep 30 / 14 / 28 / 28.

### 13. The QB's own RB only when his team is the expected winner of a high-scoring game (studies 97, 99) — *passed your rule twice: the one game-situation change that held up*
- **Study 97 (36 past slates, two random opponent sets), your request to test the shapes by game situation:** the RB mate in 4
  QB-plus-one lineups, but only for the expected winner (by 3+) of a game in the slate's top third of totals: **+0.9** against
  your book (set A +0.5, set B +1.3; about 10% more expected big wins) and **+2.3** against the RB mate everywhere. It passed your
  rule both ways and is the one game-situation version the pre-written rule picks. Small and not separable from zero; of eleven
  comparisons about three pass by chance.
- **The other versions did nothing:** the RB mate everywhere −1.4 (again, as study 96), only on expected winners −0.2, the
  favorite's RB without his QB +0.3 (your book already has that in most lineups), the trailing QB with the favorite's RB −0.7,
  QB + 2 only from high-scoring games −0.7.
- **Study 99 re-read it on a fresh set of simulated opponents: +3.4** against your book (sets +5.8 / +0.9; about 18% more
  expected big wins) and +2.8 against the RB mate everywhere. It passed your rule again: across the two studies it was ahead
  on all four opponent sets. Its best lineup also reached 200 a little more often (15.0% vs 11.1% of slates here). Still not
  separable from zero on its own. The switch is built and checked on your Week-4 book (it chose BUF, HOU and SF), and is OFF
  until you say so.

### 14. Your book without the cheap +2 block (studies 100, 101) — *information for your Week-5 trial, not a test*
- Your Week-5 trial runs the cheap +2 block in 8 lineups. Studies 100 and 101 each carried a version of your book without it,
  as a side comparison.
- **Study 100: +1.2** without the block (set A −1.0, set B +3.5; about 5% more expected big wins). **Study 101: +2.8** (sets
  +3.8 / +1.9; about 14% more expected big wins). Study 53 had read the block at about 6% fewer expected big wins. So three
  reads in the test model put the block's cost at about 5–13% of expected big wins. That is inside the trial's stop line: it
  stops if your book trails the book without the block in every live week, or falls below 0.80× its expected big wins.
- The best lineup: −0.3 and +0.1 points without the block — no change.
- **Not a test:** side comparisons on the same past slates. Your trial is judged on the real Week-5 results, where the book
  without the block is scored on paper beside yours (Monday 10-12, then 10-19).

### 15. Building lineups on their upside instead of their average (studies 102, 103) — *more 200+ lineups, fewer big wins, on every opponent set; the 8-lineup form did not hold*
- **The idea:** each player counted at his 85th-percentile score (a good day) instead of his average when the lineups are
  built — the most direct way to aim at your "scores over 200".
- **Every lineup built that way:** the book's best lineup reached 200 on **15.5% of past slates against 12.3%** for your book,
  higher on both random opponent sets (+3.2 each). **But big wins fell:** about 3.5 fewer slates in 100 with a big win (both
  sets worse), 14% fewer expected big wins, and its average finish slipped (a safety check failed). It trades big wins for
  200+ lineups.
- **Study 103, a fresh set of opponents, the same trade again:** 200+ on 16.4% of slates against 14.1% (higher on both sets),
  big wins about 3 fewer slates in 100 (both sets worse), 12% fewer expected big wins. **Across the two studies the 200+ rate was
  higher and big wins lower on all four opponent sets** — a consistent trade, not a gain by your rule (which counts big wins).
- **Only the 8 cheap-block lineups built that way:** a tiny gain in study 102 (+0.2 points on the best lineup), which **did not
  hold** on study 103's fresh set (one set below zero). So the combination with lead 13 (study 104) was not run.
- **Study 105, how much of the book on upside (13, 18 or all 26 lineups):** every amount cost big wins on both opponent sets
  (13 lineups: about 2 fewer slates in 100 with a big win; 18: about 4.5 fewer; all 26: about 3.4 fewer), and each one's average
  finish slipped. What it bought in 200+ lineups was not reliable: about 3 more slates in 100 at 13 lineups, none at 18, and 1
  at all 26 on this set (all 26 read +3 and +2 in studies 102 / 103). **There is no amount that gets more 200+ lineups without
  giving up big wins.** (Read on your book before the RB version was added.)
- **Not usable in Week 5 either way:** production has no switch for it yet (it needs an upside score around Fantasy Points'
  projections); Week 6 at the earliest.

### 16. No low-owned player at all (study 110, "LOW0") — *a small lean, not a pass: more big wins expected, one set flat*
- **The idea (from your real Weeks 1–4 fields):** your live rule allows one player predicted under 3% per lineup; this allows
  none. Top-1% lineups had no player at 5% or below about twice as often as the field, in all four weeks.
- **Study 110, on your armed book with the RB version:** **+0.3** slates in 100 with a big win (set A −0.3, set B +0.8), but
  **11% more expected big wins** (more slates with two or more) and the best lineup +1.1 points; the average finish a little
  higher. It does not pass your rule (set A just below zero). The 200+ rate unchanged.
- **On your real Week-4 book:** it would change 4 of 26 lineups (the laptop's check).
- **Versions to try later:** a fresh draw before anything else (the noise caution above); production needs the low-owned setting
  to accept 0 (today it takes only 1).

### 17. The cheap +2 block only on popular punts (study 110, "POPPUNT") — *a lean on one opponent set only*
- **The idea (your real fields):** cheap players helped when they were the popular value plays (5%+ owned), not the obscure ones.
- **Study 110:** **+1.0** (set A +2.3, set B −0.2), 5% more expected big wins; the best lineup about the same. Not your rule (set
  B just below zero). The page itself warned that one heavily played punt per week drives most of the field pattern.
- **Versions to try later:** a fresh draw; it is a variant of your cheap-block trial, so it would be judged with that trial on
  Monday 10-19.

### 18. At least 1.5 receptions a game for running backs (study 116, "REC_LOW") — *a small lean on one opponent set; idea from the same slates*
- **Your idea** ("a minimum number of receptions for a running back"), after the carries floor removed the pass-catching backs.
- **Study 116:** **+0.3** (set A +1.4, set B −0.7), 5% more expected big wins, the best lineup about the same; not your rule.
  The stricter **2.0** read **−1.4**, worse on both sets. Both cost far less than the carries floor (−4.6), as the pass-catcher
  reasoning expected.
- **Caution:** the idea came from these same past slates' real scores, so even a pass would have been "consistent", not proof.
- **Its size:** in the test model it changed about 5 of 26 lineups; its effect on your real book has not been checked. The
  laptop has built a production switch, default off (not yet merged).
- **Next, if ever:** a paper version on a live week's real results is the fair test.

## Tested and not promising (closed unless you say otherwise)
- Forced top stacks: the opponent's top receiver as the bring-back (71, 71b), QB + top pass catcher in the top games (73),
  the full game stack (74), two bring-backs (76) — each at or below your book on 2023–24.
- Choosing the QB's side of the top games (80): worse; a QB from the lower-scoring half (82): flat.
- Two $8,000+ players (78): mixed, a safety check failed.
- The three rules together (83): −1.9; on another draw +1.0 (noise).
- Your four price rules on the whole book (85): **−3.1**, 23% fewer expected big wins; defense ≤ $3,000 alone −1.1; exactly
  one receiver ≤ $4,500 alone −1.7.
- **Shrinking the projections toward the salary curve (S1, study 92): −4.4** (both draws worse), 15% fewer expected big wins —
  although its Week-4 real-contest replay had a big win (in-sample). On paper in Week 5.
- **One $8,000+ player in every lineup (S2):** failed on Week 4's real contests (50th vs 59th percentile, 2 vs 6 cashes) and read
  −5.8 in the test model. On paper in Week 5.
- No player over $7,900 in the book (86): **−4.9** (2023 −4.4, 2024 −5.5); about 18% fewer expected big wins; 2022 −0.3. Its
  real-book cost is small (−0.18 projected points per lineup; 17 of 26 lineups change), but the test model reads it clearly
  worse — the stars are worth keeping.
- Your study-87 book (87), all built without the usage caps: **the whole book −3.3** (2023 −9.0, 2024 +2.5; 2022 +3.5); about
  8% fewer expected big wins. **The price half −6.1** (2023 −6.7, 2024 −5.5; 2022 +3.6), the clearest negative of the morning,
  23% fewer expected big wins — the same as study 85's −3.1 for the same price rules. **The QB half** (top-4-game QB with his
  top receiver) **−2.3**, and below on 2022 too (−1.5). Removing the caps alone: −1.7. Against the no-caps book, the price
  rules cost −4.4 and the QB rules −0.6. Without the QB cap, one QB took up to 24 of 26 lineups.

- **Your study-87 book re-read, and a cheaper QB (study 88, your "slightly cheaper QB" request):** 87's book on a fresh draw
  **−3.1** against the live book (2022 +4.4) — about 3 points below, as on the first read. **No QB priced $7,000 or more, on top
  of it: −1.7 more** (2022 −3.3), 19% fewer expected big wins. A TE allowed in the flex: +0.2 (no change). Nothing for Week 5.

- **A defense with its own team's running back, 8 lineups (study 94): −1.0** (both random opponent sets below: −0.1, −1.9);
  3% fewer expected big wins. And in real contests it would do worse: the field already pairs a back with his own defense more
  than any other pair, which the test model's opponents do not.

- **QB + 2 lineups only from the trailing side of a high-scoring game (study 97): −5.0**, worse on both opponent sets (−6.1,
  −3.9), 13% fewer expected big wins, and 0.7 projected points per lineup lower. Trailing teams do throw more, but forcing
  those QBs into the QB + 2 lineups costs more than it gains.

- **The ceiling sweep (studies 100, 101; your "scores over 200" request):** five one-setting changes to your book — the QB in at
  most 3 lineups, at most 3 players shared between any two lineups, ownership + 10, a heavier A1 / B mix, no cheap block. None
  raised the book's best lineup by more than about a point. The one the pre-written rule picked (at most 3 shared, +0.7) read
  **−0.9 on a fresh set of opponents** and fewer big wins on both sets: the luck of the first draw. The QB in at most 3 lineups
  passed your big-win rule once (+1.7) and was mixed on the fresh set (−0.4). In the test model your book's best lineup reaches
  200 on about 12–13% of past slates whatever the setting. (At most 3 shared is planned as a paper version for Week 5.)

- **Full game stacks in the QB + 2 + bring-back lineups (study 102, your "200+" request):** the 8 A1 lineups as QB + 2 of his
  receivers + 2 opponents (up to 5 from one game) in the slate's top-4 games. **Worse on every measure:** the best lineup −1.7
  points (an interval clear of zero), about 3 fewer slates in 100 with a big win (both sets worse), 10% fewer expected big wins,
  and no more 200+ lineups (11.8% vs 12.3%). The field's 200+ lineups often look like this after the games, but building them
  before the games costs. The production switch for it stays unmerged.

- **No player projected under 8 (study 106, your question):** tested on your armed book with the RB version included. **Worse on
  both random opponent sets:** about 2.7 fewer slates in 100 with a big win, 12% fewer expected big wins, a lower average finish,
  and the best lineup 1.5 points lower. The floor removes the cheap and less-owned players the big wins draw on. So the re-check
  and the per-position floors (your follow-up, "if it's successful") were not run. In production a floor of 8 on Fantasy Points'
  projections would touch only 3 of your 26 lineups, a smaller dose of the same thing.

- **Fading players after a big game (study 109, your idea; the pros' habit):** on your armed book with the RB version, a 2-point
  fade for a player whose last game was twice his average read **−4.7** (worse on both random opponent sets, −5.7 / −3.7; 20%
  fewer expected big wins); the same at 1.6× **−5.2** (−4.0 / −6.3); and **at most one such "hot" player per lineup**, with no
  fade, **−1.8** (−2.5 / −1.2; 10% fewer expected big wins). Every version was below your book on both sets, so the fresh-draw
  check was not run. In the test model a player coming off a big game is still worth his projection.
  **Receivers and tight ends only (study 115, your "Test today for this week"):** at most one hot WR / TE per lineup **−1.6**
  (−1.0 / −2.3; 5% fewer expected big wins); 2 points off each hot WR / TE **−1.8** (−3.4 / −0.1). Smaller losses than the
  all-position versions, still worse on both sets; the fresh-draw check was not run.

- **More rules from your real Weeks 1–4 fields (study 110), each worse on both random opponent sets:** the QB only from the
  slate's three highest-total games **−3.6** (9% fewer expected big wins; the average finish lower); at most 4 of 8 players from
  the top value tenth **−2.9** (8% fewer) — it goes on paper in Week 5 so the real results can still decide it; no QB with his
  own defense plus at least $49,500 of salary **−0.6** (the floor did change lineups on some past slates, where the book's
  lowest lineup was $49,300; on your real Week-4 book the rule moves 1 lineup).

- **Usage floors (study 112, your request):** at least 13 carries a game for RBs **−4.6** (−5.2 / −4.0; an interval clear of zero,
  the clearest negative of the day; 11% fewer expected big wins), 32 pass attempts for QBs **−2.7** (11% fewer), 4.5 targets for
  WRs / TEs **−2.8** (7% fewer); each worse on both random opponent sets, the average finish lower, the 200+ rate lower. Touchdown
  and red-zone floors could not be dosed (a zero average removes every player without a recent touchdown at once) and were
  dropped before the run. With the projection floor (106), the same lesson: removing low-volume players removes the cheap ones
  the big wins draw on.
  **Double-checked at your request (10-10):** the carries numbers are right — production's carries over the last 4 games match
  an independent count from the weekly stats (correlation 0.98; only 1.5% of 2023–24 running-back weeks land on the other side
  of 13). What the floor did, by the real scores: the backs it took out of the book averaged 10.6 carries but 4.2 targets a
  game ($6,058) and scored 14.3 DraftKings points, with a 20+ game 26% of the time; the backs that replaced them averaged 15.5
  carries and 3.0 targets ($6,428) and scored 13.1, with a 20+ game 18% of the time. In DraftKings scoring a catch is worth a
  point, so the pass-catching back with 10 carries often beats the 15-carry grinder; a carries floor removes exactly him.

- **Your 10-09 evening question — correlations that could give an edge (three quick screens on your real Weeks 1–4; the plan
  was written down before any result was read):**
  - *Defense strength normalized like DVOA:* already in our model (each defense's points allowed to a position, adjusted for
    the offenses it faced, last six weeks), and it adds almost nothing; the plain matchup bonus read flat three times (studies
    50, 51 and the Week-5 paper arms). Fantasy Points' projection prices matchups too.
  - *A receiver's points per route against THIS defense's man / zone mix (Fantasy Points' coverage data):* **no signal** over
    four weeks (−0.02; Week 3's hint did not hold).
  - *Receivers whose route share just jumped or fell (regression to the mean):* **no signal** (−0.04).
  - *Does the crowd know something? (ownership as a forecast):* **yes, against OUR old projections** — players the field liked
    more than their projection and price said beat our projection (top fifth +0.8 points a player, bottom fifth −0.5; passed
    its test), mostly in Weeks 1–2. **But against Fantasy Points' projection (Week 4, the only week with both) it adds nothing**
    (+0.01): FP's projection already carries what the crowd knows. That is why switching to FP and the ownership cap point the
    right way; it is not a new lever on top of them.

## Still running
- **Last, by your order (study 114):** removing one live rule at a time from your armed book.

*Updated as each study is read.*
