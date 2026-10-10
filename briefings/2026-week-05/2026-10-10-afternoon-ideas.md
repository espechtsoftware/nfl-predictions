# Saturday afternoon: where the room is, and three things that could still change Sunday's chances (2026-10-10)

**For:** Erich, and the laptop and reviewers. Written by the outside model after your "we are done with all of the experiments
... five hours until the build ... any ideas that can help me win a big prize more often ... boom players, core players, how
the rules are structured." Read for it: today's reads (106–116), the laptop's scoring run of the armed book on this season,
the armed book's players and games on Week 4's slate, the open-defects register, and the field screens of this week.

## In one page

**Where the book stands.** The laptop's run of the full armed book on this season (12:58): the best lineup scored 177.9 on
Week 4 (about the top 1.5% of the Millionaire; the top-1% line 182.8; the winner 234.2) and 162.7 on Week 3 (top 9%; the line
188.2; the winner 239.8). No lineup reached 180 in either week. A big win in your contests needs roughly 190–210. That gap,
15–45 points on the best lineup, is not the size of anything a rule tweak moves: fifty-odd rules read ±3 points this week and
none moved the ceiling; the rule-removal study (114) says the eight rules you run are each helping or a wash. **The structure is
sound. The core players are the right kind.** The book's heaviest players (9 of 26 lineups each) are volume players: running
backs at 45–73% of their team's carries, receivers at 24–33% of targets running 78–98% of routes, one cheap tight end at 19% of
targets. That is the regulars' core too (volume backs, high-target receivers, a cheap high-target TE). Nothing to fix there.

**Where the points are.** Three places, in the order I would spend the five hours:

| # | What | Why it is where the points are | What it takes today |
|---|---|---|---|
| 1 | **Wire the late-scratch next-man-up bump (O-60) for Sunday** | The players who made Weeks 2–4's winning lineups were next-man-up plays: Schultz (Collins out → 14 targets), Hockenson (Jefferson out → 13), Warren (Dowdle out, 90% of snaps), Flowers (Bateman out in-game). When a scratch comes after Fantasy Points' last update, the book keeps the pre-scratch numbers for the whole team; FP's own history shows what the bump is worth when FP does know (a WR ruled out → his teammates +15 points). The fix is built (15 tests, default off), not wired; its deadline is Week 6 | A money-path change on arm day: wire, the Week-4 gates with it off (byte for byte), one ON check, the `--check`, in by about 17:00; otherwise Week 6 as planned. Not a rule, not a bet: it only acts when a scratch lands after FP's update |
| 2 | **Hedge the game bet on paper this week: a cap on the top-total game's QB rows** | On Week 4's slate the book puts 10 of 26 lineups on the top-total game's two quarterbacks and 4 on each of the next two games. The Millionaire was won from the second- or third-highest total by a favoured QB in Weeks 1, 3 and 4; the top-total game is the week's top-scoring game only 16–19% of the time. Every game-coverage rule read flat or worse in the harness (43, 16, 24, 47) — on its own projections, against an easier field; the fields say the opposite | A study-38 paper arm (TOPCAP6: at most 6 rows on the top-total game's QBs; the rest unchanged), so Sunday's real field scores it beside the book. One amendment, as 6y / 6z were |
| 3 | **Your touchdown-odds upside block (row 48) on paper** | The one upside signal that held in your real fields (3 of 4 weeks): cheap players whose anytime-TD price beats what their salary implies. The harness cannot read it (the props history is thin), which is why it has waited. The block vehicle exists and the props are pulled Sunday morning | A block file from Sunday's 04:30 props snapshot (the cheap-block file pattern) and a paper arm; if the file step does not fit Sunday's chain, Week 6 |

**And one process change for Week 6, decided now, before Sunday's results are seen.** The harness and the real fields disagree
on every input-level rule this week (hot WR/TE, value density, stars, the fade), and the harness is built on its own
projections for 2023–24. The paper co-run on real fields (study 38) is the right judge for those, but its rule needs four
weeks all positive, which is slower than your horizon. **Set a two-week rule now** for the arms with field support (HOT1,
HOT_WRTE1, VAL4, S2 stars, NOTERM, MS3, and TOPCAP6 above): an arm that beats the live book on the big-win chance in both
Week 5 and Week 6 is adoptable for Week 7, by your decision. Writing the rule before the results exist is what keeps it a
test.

**What I would not do this afternoon:** another harness study. Fifty reads this week passed none that held, and a new arm has
about a one-in-three chance of a false pass with no time left for the fresh-draw check. The machine's better use is item 1.

## 1. The book on Week 4's slate: games and quarterbacks

| QB game, by total rank | Lineups of 26 | Note |
|---|---|---|
| 1 (51.5): both sides | **10** | 5 + 5; the ownership cap keeps either QB at 5 |
| 2 (50.5) | 4 | the favourite's side |
| 3 (48.5) | 4 | the game that decided Week 4 (227 points, 70 of the top 100) |
| 4 (48.5) | 2 | |
| 6 (44.5) | 3 | |
| 12 (38.5) | 3 | |

Eight quarterbacks, six games, 5.15 games touched per lineup. Before the package the top game held 91% of the entries' QBs
(the pre-mortem); it now holds 38%. The field's top 1% in Weeks 1–4 used QBs ranked about 10th by our projection; the book's
run 1–8.

## 2. The core, by the numbers (the 9-lineup players)

| Position | Salary | FP proj | FP own | Carry share | Target share | Route share | Snap share |
|---|---|---|---|---|---|---|---|
| RB | $6,100 | 18.2 | 26% | 0.73 | 0.13 | 0.55 | 0.71 |
| RB | $6,000 | 18.1 | 26% | 0.64 | 0.09 | 0.45 | 0.69 |
| WR | $6,500 | 17.7 | 23% | — | 0.30 | 0.78 | 0.74 |
| WR | $5,300 | 15.6 | 24% | — | 0.24 | 0.88 | 0.90 |
| RB | $7,700 | 22.8 | 30% | 0.45 | 0.21 | 0.73 | 0.63 |
| RB | $5,800 | 16.5 | 22% | 0.54 | 0.11 | — | 0.49 |
| TE | $3,300 | 11.4 | 21% | — | 0.19 | 0.67 | 0.73 |

Seven players at the 9-row cap, six more at 7–8. These are volume plays, owned 21–30% by the field's projection: the
regulars' core (the 10-06 report: expensive volume backs, high-target receivers, a cheap high-target TE, no QB core). The
"boom" kind the book never buys is the expensive receiver in the second- or third-total game (Lamb, 24th by value on Week 4):
that is the star rule, on paper this week as S2; nothing more to do today.

## 3. The three items, in detail

**1. O-60.** `reports/OPEN-DEFECTS.md` O-60: "FP replaces our next-man-up bump for late scratches FP has not yet processed";
branch `review/late-scratch-bump-20261008` @ `fbad73be`, default off, not wired, 15 tests; depends on O-59 (the 10:47 pull,
merged) and O-16 (`--dk-status`, open); deadline "before the W6 T-70 build". Why it ranks first: of the twelve winners' players
we missed in Weeks 1–4 (`reports/2026-10-07-why-we-missed-the-winners-players.md`), four were pre-lock injury beneficiaries and
the ones we did have (Schultz, Hockenson, the Jets stack) were all vacated-target plays; a scratch after FP's update is the one
case where the book is blind to exactly that. Its cost is zero on a week with no late scratch. Whether it is safe to wire on
arm day is the laptop's and reviewer's call; the Week-4 gates with the switch off must stay byte for byte.

**2. TOPCAP6 on paper.** Every harness read of game coverage was negative, and all of them were built on the lab's own
projections, which rate the top-total game's players highest; 2023–24 realized results then rewarded that. The 2026 fields say
the winners came from ranks 2–3 three weeks out of four, and the Week-4 book had 10 lineups on rank 1 and 4 on the game that
decided the week. The honest test is the real field: a paper arm with at most 6 rows on the top game's QBs (the solver refills
the rest from the next games), read Monday beside the book. Prior: no difference in expectation; the value is in the weeks the
top game is not the top-scoring game, which is most weeks.

**3. The TD-odds block on paper.** Row 48's definition, from the field check: a sub-$7,000 RB / WR / TE whose last pre-lock
anytime-TD probability sits more than one standard deviation above what his salary implies (within position). Lineups carrying
more of them had higher top-1% rates in Weeks 1, 2 and 4; the simulator's own upside measure went the other way all four weeks.
The block vehicle gives +2 to those players in the 8 block rows, in place of or beside the cheap +2 (the cheap set is the
natural superset). It needs the props snapshot after the 04:30 pull, so the file is a Sunday-morning step; if the snapshot chain
cannot take it this week, it is the first Week-6 paper arm.

## 4. Limits

The scoring run is in-sample and two weeks (W3 approximate). The game-coverage pattern is four real weeks against two harness
seasons. The core-player profile is one slate. O-60's value depends on whether a relevant scratch lands after FP's update on a
given Sunday; most weeks have one or two.

## 5. Sources

HANDOFF 2026-10-10 12:58 (the scoring run), 12:30 (study 114), 10:20 / 11:30 / 09:23 / 08:23 (studies 112, 116, 115, 110);
`reports/OPEN-DEFECTS.md` O-59, O-60; `reports/2026-10-07-why-we-missed-the-winners-players.md`;
`briefings/2026-week-05/2026-10-08-necessary-players-and-the-bring-back.md`; `reports/2026-10-07-winners-strategy-study/`
(`cheap_upside_field.py`, the environment forms); the Sunday construction on Week 4 from `~/rehearsals/minprojcheck-live-20261010T102003Z/LIVE`
with `~/moneygate/inputs/own/w4_ownership_fp.csv`; `reports/2026-10-04-post-week4-study-list.md` row 48; the study-38 prereg §5.
