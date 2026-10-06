# Week 5: your decisions (draft for Friday)

2026-10-05, written for you; revised 10-06 for your revised entries and your goal. Each decision is reversible, and
none is armed without your yes. The contest plan's dollars are in your private files, not here (this repository is
public).

**Your goal, in your words (10-05):** "If i could win one 333, 555 or 4444 or $500 in the milly, the week is a success
and i wouldnt care if i lost all the $20 milly tickets." So from now on the number that matters is **the chance of at
least one big win in the week**: a $333 or bigger seat, or a $500+ finish in the Millionaire. Average tickets come
second.

## The short version

| # | Decision | My recommendation |
|---|---|---|
| 1 | The lineup shape: WS, the shape-mix portfolio (MIX), or today's | **WS**: the only change that passed its test |
| 2 | Fantasy Points' projections instead of ours | **Yes** (you decided this in principle; the Week-4 check worked) |
| 3 | The lab-code update both of these need | **Yes**: it changes nothing when they're off (proven below) |
| 4 | The Week-5 contest plan | **Done: your revised entries** (19 contests, 24 entries) |
| 5 | Every entry a different lineup | **You chose this.** Study 24 checks it against your goal; result Wednesday |
| 6 | A cap: no game's quarterbacks in more than 6 of your 24 entries, on top of 5 | **Decide after study 24** (Wednesday) |

## 1. The lineup shape

**What we tested.** Study 18 rebuilt the book on 53 practice slates (2022–24) in three ways. It used the cash lines of
my first draft plan (9–22% of the field paid):

| Version | What every lineup looks like | Tickets vs today's | Average finish | Slates with no ticket |
|---|---|---|---|---|
| Today's | QB + 2 pass catchers + an opponent bring-back, always | — (737 tickets) | — | 10% |
| **WS** | QB + 1 pass catcher, a player from each team of a second game, at most 3 from the QB's game, rarely a bring-back | **+42% (1,047)**, every season better | **up ~3 points** | 15% |
| MIX | the winners' mix: 30 / 14 / 28 / 28% of four shapes | +16% (856), not conclusive | up ~1 point | 15% |

- **WS passed** the frozen test, which was written before any results were seen. That is the bar we use.
- **The cost:** a noticeably wider swing. Slates where the whole book wins nothing rise from 10% to 15%, and on the
  worst tenth of slates the average entry beats 22% of the field instead of 28%. More tickets on average, bigger swings.
- **Your plan's lines are deeper than the ones tested.** Your revised plan's seats sit at the top 1–4% of each contest
  (one seat in 23 to 402), not at 9–22%. WS's better average finish should help there too, but the +42% is a number for
  shallow lines, not for your plan. Study 24 runs on your actual plan and reports WS's own chance of at least one big
  win (Wednesday).
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

## 4. The Week-5 contest plan: your revised entries

- **19 contests, 24 entries**, built from your revised entries file. The baseball satellites are gone, and your two
  entries in the $555 super-satellite are in.
- **Almost all of it chases big seats:** the $333 Wildcat, $555 and $4,444 satellites and the World Championship
  qualifier, one entry each except the cheapest Wildcats (two each); two Millionaire entries; one entry in the $20-ticket
  super-satellite, the only contest that does not pay a big seat.
- **One of the $4,444 satellites seats the October 12 Showdown** (a single-game contest), not the main-slate $4,444.
  It counts as a big win: your words to the reviewer, "any one except a $20 milly ticket count as big wins to me".
- **Everything in study 24 uses this exact plan**, with the Millionaire judged at the $500+ line (the top 95 of
  161,764).

## 5. Every entry a different lineup

- **Your choice (10-05):** "All distinct." The build then makes 24 lineups, one per entry, instead of putting the best
  four lineups in two contests each.
- **One wrinkle:** a rule that stops two entries in the same small contest from sharing more than 5 players can still
  reuse a lineup. In the reviewer's trial runs, 21–22 of 24 entries were distinct, not 24.
- **Study 24 decides on strictly distinct (24 of 24) against today's dealing,** judged by your goal. Strictly distinct
  needs a small, reviewed change to the build before Saturday: it builds a few spare lineups to swap in.
- **The build's sequential dealing as it stands** (no code change; 21–22 of 24 distinct) is measured too, as the fallback
  if the change isn't ready.

## 6. A cap on any one game

- **Why:** concentration. When one game carries most of the book and disappoints, most entries lose together. That
  hurts your goal (one big win) more than it hurts average tickets.
- **How often it happens,** rebuilt on Week 4: the share of entries whose quarterback came from the slate's
  highest-total game.

  | Book (Week 4) | Entries whose QB is from the highest-total game |
  |---|---|
  | What we entered | 62% |
  | WS | 34% |
  | WS + FP | 53% |
  | MIX + FP | 77% |
  | The field | about 20% |

- **It is not only the top game.** In the reviewer's trial run, WS put 21 of 24 entries on ONE game's quarterbacks,
  and that game was not the highest-total one.
- **So study 24 tests a cap on every game:** no game's quarterbacks in more than 6 of your 24 entries. Other players
  from that game can still appear as bring-backs and second-game pairs.
- **It is tested on top of all-distinct dealing,** the package you would run. With the old dealing, the rule that stops
  two entries in the same small contest from sharing more than 5 players swaps the second entry onto another lineup,
  sometimes one from a game already at its limit, so the cap leaked to 8 of 24 in the trial run. All-distinct draws
  those swaps from spare lineups the cap already governs, and held it at exactly 6.
- **Judged by your rule:** the cap passes only if it raises the chance of at least one big win, keeps the average
  finish, and costs at most about 20% of expected big seats. Your words: "judge the entry cap by chance of at least one
  big win (seats of $333+ or $500+ Milly), not average tickets, accepting up to ~20% fewer expected big seats if
  average finish holds."
- **If it passes and you say yes:** I build it into the live build with a check that it matches the study, call for
  call; the reviewer reviews it before Saturday. If it fails or reads "no difference," it is not offered as a passed
  test.

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
  `UNION_MAIN=mix UNION_MIX_PORTFOLIO=ws UNION_PROJ_SOURCE=fp`, with the lab pin moved to the new code, plus the
  dealing setting and, if adopted, the game cap. The arming banner prints the choice, so a missed line can't silently
  pick the wrong arm.
- **Safety nets:**
  - if WS can't fill the book, the build falls back loudly to today's shape;
  - if FP's capture fails a check, it falls back loudly to our projections;
  - every audit and Sunday's replacement of ruled-out players already understand the new shapes.
- **Undo:** remove those settings and move the pin back. Today's build is unchanged.
- **Monday:** the entered book against a paper rebuild of today's book on the same slate, plus the shape you actually
  entered, the ours / FP / blend accuracy, and the week judged by your goal (any big win, and how close the best
  entries came).
