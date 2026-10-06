# Week 5: your decisions (draft for Friday)

2026-10-05, written for you; revised 10-06 for your revised entries and your goal. Each decision is reversible, and
none is armed without your yes. The contest plan's dollars are in your private files, not here (this repository is
public).

**Your goal, in your words (10-05):** "If i could win one 333, 555 or 4444 or $500 in the milly, the week is a success
and i wouldnt care if i lost all the $20 milly tickets." So from now on the number that matters is **the chance of at
least one big win in the week**: a $333 or bigger seat, or a $500+ finish in the Millionaire. Average tickets come
second.

**What to expect:** your plan wins at least one big seat in about 1 in 4 practice weeks with an easier field (study
24). Real satellite fields are tougher, so the chance is lower in practice.

## The short version

| # | Decision | My recommendation |
|---|---|---|
| 1 | The lineup shape: WS, the shape-mix portfolio (MIX), or today's | **Your preference, not a tested gain:** on your plan and goal WS and today's shape tied (study 18b). Doing nothing keeps today's |
| 2 | Fantasy Points' projections instead of ours | **Yes** (you decided this in principle; the Week-4 check worked) |
| 3 | The lab-code update both of these need | **Yes**: it changes nothing when they're off (proven below) |
| 4 | The Week-5 contest plan | **Done: your final entries (Rev2)**: 29 contests, 53 entries; the super-satellites reuse your top lineups |
| 5 | Every entry a different lineup | **Keep today's dealing.** Your Rev2 pins the super-satellites to your top lineups, and the sequential dealing would ignore those pins (it now refuses) |
| 6 | A cap: no game's quarterbacks in more than 6 of your 24 entries | **No:** it didn't raise your chance of a big win and cost 22% of expected big seats |

## 1. The lineup shape

**The test that answers your question (study 18b, 10-06): a tie.** It rebuilt your exact plan on 53 practice weeks
under the live build's limits and compared WS with today's shape by your goal. It was written before any results and
re-run by both of us with identical output.

| Today's shape vs WS, on your plan | Today's | WS |
|---|---|---|
| Chance of at least one big win in a week* | about 1 in 4 | +0.6 points: **no difference** (range −7 to +8) |
| Expected big seats | — | 3.5% fewer |
| Average finish (share of the field beaten) | 49.9% | 51.2% |
| Weeks with almost no chance of a big win | 48% | 36% |
| Weeks where the best lineup reached 200 points | 9.4% | 7.5% |
| The worst tenth of weeks (average finish) | 27% | 20% |

\* Practice weeks with an easier, Millionaire-style field; lower in practice.

- **So the shape is a preference, not a tested gain.** WS gives a better average and fewer near-dead weeks. Today's
  shape gives a slightly higher ceiling and holds up better in its worst weeks.
- **Doing nothing keeps today's shape.** WS is now safe to run (the Sunday replacement fix), so it is a fair choice if
  you prefer its profile. I would not switch to it expecting more big wins.
- **Why study 18's +42% didn't carry over:** that gain was at shallow lines, where 9–22% of the field is paid. Your
  satellites pay only the top 1–4%, and there today's tighter stack keeps pace.

**The earlier test (study 18), for the record.** It rebuilt the book on 53 practice slates (2022–24) in three ways,
using the cash lines of my first draft plan (9–22% of the field paid):

| Version | What every lineup looks like | Tickets vs today's | Average finish | Slates with no ticket |
|---|---|---|---|---|
| Today's | QB + 2 pass catchers + an opponent bring-back, always | — (737 tickets) | — | 10% |
| **WS** | QB + 1 pass catcher, a player from each team of a second game, at most 3 from the QB's game, rarely a bring-back | **+42% (1,047)**, every season better | **up ~3 points** | 15% |
| MIX | the winners' mix: 30 / 14 / 28 / 28% of four shapes | +16% (856), not conclusive | up ~1 point | 15% |

- **WS passed** that frozen test on tickets at shallow lines. Study 18b (above) is the test on your plan and goal.
- **The cost:** a noticeably wider swing. Slates where the whole book wins nothing rise from 10% to 15%, and on the
  worst tenth of slates the average entry beats 22% of the field instead of 28%. More tickets on average, bigger swings.
- **Your plan's lines are deeper than the ones tested.** Your revised plan's seats sit at the top 1–4% of each contest
  (one seat in 23 to 402), not at 9–22%. WS's better average finish should help there too, but the +42% is a number for
  shallow lines, not for your plan. Study 18b answered it on your plan: a tie (above).
- **MIX** is the "mix of shapes like the winners" you asked for. It moved the right way but was not conclusive.
- **Your literal dual stack** (QB + 1 + bring-back + a second-game pair, on every lineup) was tested as EXPLORATORY.
  - It got about half WS's gain (+2.2 tickets per slate) with the steadiest results of any version: no ticket on 9% of
    slates, the worst tenth at 34%, the average finish up about 3 points.
  - Exploratory versions can't be adopted without a confirming test, so it is information, not an option this week.
- **Rules that spread the book across more players** (study 17: diminishing returns, expected-max, pool-greedy) did
  not pass. They trade expected tickets for fewer empty weeks. Today's selection stays, and the shape change carries
  the diversification.
- **On your "not one strategy everywhere":** WS is one shape, but a much looser one than today's: about 4.8 games
  per lineup, against 4.3. A further idea, by contest type (WS for qualifiers, today's tighter stack for any
  Millionaire entries), is on the study list as item 23.

## 2. Fantasy Points' projections

- **Your decision (10-05):** use FP's instead of ours, unless ours or a blend beats them.
- **Week 4, the only week with FP data, corrected 10-06** (the frozen weekly check, players who actually played):
  - average miss: **FP 5.54 points, ours 5.58, a 50/50 blend 5.52**;
  - all three are within noise of each other: FP beat ours in about 2 of 3 resamples of the games, and the blend beat
    FP in about 2 of 3;
  - my 10-05 figure (FP 5.47 vs ours 5.56) counted three players who turned out inactive. FP had already zeroed two of
    them; ours had not. That part of FP's edge is real but different: FP knew about the 10:30 inactives at 10:40, and
    DraftKings had not yet marked those players OUT at our 10:33 pull. With FP's numbers, the build won't pick a
    just-ruled-out player. Our check before upload (DraftKings' live statuses, about 11:00) catches them either way.
- **Your rule** ("use fantasy points unless ... our projections or the blend have beat them") stays the test. The
  frozen weekly check calls it "beat" only when the weeks pooled show a lower average miss in at least 95% of
  resamples. Week 4 alone doesn't meet that for anyone, so FP stays the choice.
- **Expect "nobody beats FP" for several weeks.** With about 195 players a week, a real difference of a tenth of a
  point takes several weeks to show at that level. So that answer is the default for a while. It is not evidence that FP
  is better.
- **What changes:** FP's numbers pick the lineups. They are captured at 10:40 Sunday, after the inactives, and matched
  exactly by DraftKings' player ID. If the capture is missing or looks wrong, the build falls back to ours and says
  so loudly.
- **One limit:** FP gives an expected score only, so our simulations still drive the "chance to cash" estimates.
- **Every Monday:** I report ours vs FP vs the blend. That is your condition for revisiting.

## 3. The lab-code update

- **Why it's needed:** both WS and MIX need a new option in the lab's lineup solver. It is a one-change update to the
  code the build uses.
- **Proof it is safe when off:** I rebuilt Week 4's actual book on the new code with the new options off. It matched
  what we entered, byte for byte.

## 4. The Week-5 contest plan: your final entries (Rev2, 10-06)

- **29 contests, 53 entries**, built from your final entries file (Rev2). It keeps everything below and adds:
  - **the $20-Millionaire super-satellites** (the cheap 25-seat ones), 27 entries in all. Your words: "For those, I
    only want to reuse my top lineups that I'm using elsewhere. I don't want to have one of those do better than a big
    contest and feel bad that I should have entered it elsewhere. My hope with those is to win many". So each of them
    gets your top lineups (rows 1–5, 1–3, 1–2 or 1), never a lineup of its own;
  - **the $125 World Championship satellite**: not a big win, and it reuses your top lineup (your words: "the 125
    WFFC one doesn't and it should reuse an entry");
  - **three Midseason Warm Up Millionaire satellites**: they count as big wins (your words: "the midseason ones count
    as big wins") and get lineups of their own.
- The book is 22 lineups (it was 20); every other contest is dealt as before.
- **The earlier plan (Rev1, below) is what studies 24 and 18b tested.** Rev2 adds cheap contests that reuse the
  same lineups, so those results carry over; the reviewer's study 26 already runs on Rev2.

**Rev1, for the record:**
- **19 contests, 24 entries**, built from your revised entries file. The baseball satellites are gone, and your two
  entries in the $555 super-satellite are in.
- **Almost all of it chases big seats:** the $333 Wildcat, $555 and $4,444 satellites and the World Championship
  qualifier, one entry each except the cheapest Wildcats (two each); two Millionaire entries; one entry in the $20-ticket
  super-satellite, the only contest that does not pay a big seat.
- **One of the $4,444 satellites seats the October 12 Showdown** (a single-game contest), not the main-slate $4,444.
  It counts as a big win: your words to the reviewer, "any one except a $20 milly ticket count as big wins to me".
- **Everything in study 24 uses this exact plan**, with the Millionaire judged at the $500+ line (the top 95 of
  161,764).

## 5. Every entry a different lineup: tested (study 24)

- **You chose "All distinct" (10-05) before this result.** Study 24 tested it on your exact plan, judged by your goal.
  It found **no gain from it, and a small cost in average finish.** The test was written before any results and re-run
  by both of us with identical output.
- **Doing nothing means today's dealing:** the best 4 lineups go in two contests each.

  | Dealing | Chance of at least one big win in a week* | Expected big seats | Average finish | Distinct lineups |
  |---|---|---|---|---|
  | Today's (the default) | about 1 in 4 | — | 50.1% | about 19 of 24 |
  | Strictly distinct | +1 point: no difference | 5% fewer | 48.6% | 24 of 24 |
  | The build's sequential dealing (no code change) | +3 points (a side arm, not a passed test) | 4% more | 49.3% | about 22 of 24 |

  \* On 53 practice weeks with an easier, Millionaire-style field. Real satellite fields are tougher (the regulars
  are a bigger share), so the chance is lower in practice. Our simulations put it near 1 in 2, which is why we don't
  quote simulated odds of a big win. The differences between the rows are what the test measures.
- **Strictly distinct: no difference** in your chance of a big win (+1 point; the test's range runs from −3 to +5). It
  costs about 1.6 points of average finish, because the extra lineups it needs are weaker ones. **Not recommended,**
  and the code change is not being built.
- **The build's sequential dealing** had the best numbers: +3 points of chance, 4% more expected big seats, and about 22
  of 24 lineups distinct. But it was measured as a side arm, not the deciding one, so it is not a passed test. It costs
  about 0.8 points of average finish.
- **Why sequential beats strictly distinct:** putting a strong lineup in a second contest beats replacing it with a
  weaker spare.
- **My recommendation (updated for Rev2): keep today's dealing.** Your Rev2 pins the super-satellites to your top
  lineups, and the sequential dealing has no way to honour those pins: it would give each of them new, weaker
  lineups, against your instruction. The build now refuses that combination outright. Sequential also showed no
  proven gain, so nothing is lost.

## 6. A cap on any one game: tested (study 24), not offered

- **Why it was tested:** concentration. When one game carries most of the book and disappoints, most entries lose
  together. Rebuilt on Week 4, the share of entries whose quarterback came from the highest-total game:

  | Book (Week 4) | Entries whose QB is from the highest-total game |
  |---|---|
  | What we entered | 62% |
  | WS | 34% |
  | WS + FP | 53% |
  | MIX + FP | 77% |
  | The field | about 20% |

  On the practice slates, today's book put about half your entries on one game's quarterbacks, often not the
  highest-total game.
- **What was tested:** no game's quarterbacks in more than 6 of your 24 entries, on top of all-distinct dealing.
- **Result: no gain toward your goal,** and it fails your limit:
  - the chance of at least one big win: −2 points (the test's range runs from −8 to +3);
  - expected big seats: 22% fewer, past your "up to ~20% fewer";
  - fewer weeks with almost no chance (39% of slates against 44%), but a lower ceiling.
- **So it is not offered,** and it is not being built. Study 1 found the same trade: steadier weeks, fewer big ones.

## The Week-4 replay: one week, a check that it all works, not evidence

The arms are rebuilt from Week 4's real pre-lock inputs and scored on the real Week-4 contests. "Return per $1" is
winnings over fees; "average finish" is the share of the field beaten.

| Book | Return per $1 | Cashes | Average finish |
|---|---|---|---|
| What we entered | 0.17 | 2 | 44.7% |
| Same, rebuilt on the new code | 0.17 | 2 | 44.7% (identical) |
| + FP projections | 0.00 | 0 | 46.6% |
| MIX | 0.17 | 2 | 49.2% |
| MIX + FP | 0.52 | 6 | 57.1% |
| WS | 0.43 | 5 | 48.5% |
| WS + FP | 0.43 | 5 | 53.0% |

**Read this table as a working check, not as evidence.** One week's cash counts are mostly luck. The 53-slate test in
section 1 is the evidence.

## What we have not tested, said plainly

- **The combination is untested as a whole.** Studies 17, 18 and 24 run on OUR simulated projections, without the
  ownership adjustment. "WS + the ownership adjustment + FP projections" as a combination is untested except by the
  one-week Week-4 replay. There is no FP data for 2022–24, so a full test of the combination is not possible.
- **The live build limits every player to half the lineups; the tests did not.**
  - Your 24 entries come from a 24-lineup book (20 with the old dealing), and no player can be in more than half of it.
  - The studies built 105 lineups and dealt the best 24. Their player limit (52 of 105) never applied within those 24,
    so one player sat in nearly every entry (about 98%).
  - So the live book spreads its players more than study 18's books did, and study 18 doesn't cover that difference.
    (I wrote on 10-05 that the limits were "the same shares". That was wrong; corrected 10-06.)
  - **Study 24 was changed to match the live build** before any of its results existed: each version is built with
    the live limits (half the lineups per player, a quarter per defence). So its verdicts are about the package the
    build would actually run.
- **The fields are modelled, not real.** Study 24 models every contest's opponents as Millionaire-style entries.
  Real satellite fields are smaller and sharper (the regulars are a much bigger share of them), so its absolute
  chances are optimistic. The comparisons between versions are what it decides on.

## If you say yes: how it runs and how we undo it

- **Arming:** the Saturday arming line adds
  `UNION_MAIN=mix UNION_MIX_PORTFOLIO=ws UNION_PROJ_SOURCE=fp`, with the lab pin moved to the new code, plus
  nothing for the dealing (today's head dealing stays; your Rev2 pins need it). The arming banner prints the choice, so a missed line can't silently
  pick the wrong arm.
- **Safety nets:**
  - if WS can't fill the book, the build falls back loudly to today's shape;
  - if FP's capture fails a check, it falls back loudly to our projections;
  - every audit and Sunday's replacement of ruled-out players already understand the new shapes.
- **Undo:** remove those settings and move the pin back. Today's build is unchanged.
- **Monday:** the entered book against a paper rebuild of today's book on the same slate, plus the shape you actually
  entered, the ours / FP / blend accuracy, and the week judged by your goal (any big win, and how close the best
  entries came).
