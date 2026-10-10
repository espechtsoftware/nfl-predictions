# Week 5, Saturday morning: the shape percentages and the game-situation rules (2026-10-10)

**For:** Erich, first thing Saturday, before the 10:28 arming. Written by the outside reviewer; the lab reviewer read every
study and the laptop re-ran every read with identical output. **Your rules last night:** no questions to you overnight; "If
something is successful, we'll discuss in the morning how we want to use it."

## The short version

**One decision for you this morning — DECIDED: adopted (armed).** The RB version below (the QB's own RB, only for the expected
winner of a high-scoring game) is armed for Week 5 (RB_MATE_C = 4, RB_MATE_SCOPE = favhi; your words: "Yes, it seems the RB one
should be adopted."; production `e8a4d0a4`, FRIDAY_HEAD `b00c5e43`). **Everything else: Week 5 as armed** — no other change held
up overnight.

- **Shape percentages (studies 95 and 98): keep today's A1 30% / A2 14% / B 28% / C 28%.** Your mix held up — removing A1, B
  or C was worse on both opponent sets. The rule fixed beforehand suggested a small shift (A1 39% / A2 12% / B 24% / C 24%), but
  on a fresh draw (study 98) it was no better on one of the two opponent sets (+0.6 overall, a coin flip), so it is not
  suggested.
- **Game situations (studies 97 and 99): one version passed, and it HELD on a fresh draw** — **the QB's own RB in 4 QB + 1
  lineups, only when his team is the expected winner of a high-scoring game.** Study 97 +0.9 (×1.10 expected big wins), study 99
  +3.4 (×1.18): better on all four opponent sets. Its 200+ rate was a little higher on both reads (12.7% vs 11.8% in 97,
  15.0% vs 11.1% in 99), as were several other versions' (the 200+ rate is noisy at about 12%). Still not clear of chance on
  its own; **you adopted it: armed for Week 5** (RB_MATE_C = 4 with RB_MATE_SCOPE = favhi). The shootout QB + 2 did not pass (−0.7, then +0.5 split); the
  trailing-side QB + 2 was worse both times (−5.0, −5.6).
- **The RB stack mate, unconditioned (study 96): paper only.** On top of the one-receiver-per-team rule it read −0.5 (worse on
  both opponent sets), although every lineup got its RB. It stays off (RB_MATE_C = 0) unless you choose a version below.
- **Raising the ceiling (studies 100–103, your "200+" notes):** five simple settings barely moved the best lineup, and the
  best of them (overlap 3) did not hold on a fresh draw: **keep your live settings** (studies 100 / 101). Three new
  constructions for the ceiling (study 102): building **every** lineup on upside raised the 200+ rate (15.5% vs 12.3%) but cost
  big wins (×0.86, worse on both sets); the full game stack was worse on everything; the pick (only the 8 cheap-block lineups on
  upside, +0.2) did not hold on a fresh draw (study 103). Building every lineup on upside repeated its trade in study 103: more
  200+ lineups on all four opponent sets (+2–3 slates in 100), fewer big wins on all four (12–14% fewer expected). **Keep your
  live settings.**
- **Already armed for Week 5 (your decisions):** Fantasy Points' projections, the winners' shape mix, the cheap +2 block, the
  35% cap with the ownership limit (+ 15), at most one TE and one player under 3% per lineup, and one receiver per team in the
  QB + 1 lineups. (The cheap +2 block is entered at Saturday's arming, as designed: TERM_ROWS = 8.)

**How to read the numbers:** "+2.0" means about 2 more slates in 100 with a big win, on the test model (36 past slates of
2023–24, scored on their real results, against two separate random sets of opponents, "A" and "B"). **Your rule** for a change:
better on both opponent sets, without losing more than 20% of expected big wins. **Under no real effect a change passes that
rule about one time in three or four.** Studies 95 and 97 make 19 such comparisons (95: 8, 97: 11), all on the same 36
slates as studies 89–96 — so about five to six passes are expected by chance alone, and a pass is a candidate, not proof.
That is why each pick was re-run on a fresh draw (studies 98 and 99); the ceiling studies 100 and 102 add eight more
comparisons, each with its own fresh-draw check. **The test model builds lineups from its own simulated projections; your book
uses Fantasy Points', so a gain there may not carry over** (studies 91 and 92 showed both directions). The laptop's Week-4
check shows what a change does to your real book.

## About "200+ fairly regularly" (your note to the laptop last night)

From your real Weeks 1–4 fields (the laptop's count, HANDOFF `3ac3bfd7`; aggregates only):

| Week | Share of the field at 200+ | The field's top 0.1% starts at | The field's best | Our best entry |
|---|---|---|---|---|
| 1 (a high-scoring week) | 2.3% | 229.5 | 274.0 | 196.2 |
| 2 | 0.10% | 200.3 | 235.5 | 156.2 |
| 3 | 0.25% | 206.0 | 239.8 | 178.9 |
| 4 | 0.18% | 205.4 | 234.2 | 182.6 |

- **Where 200 sits:** in a normal week it is a top-0.1–0.25% score. Our best entry came within 4 points in Week 1 (196.2); none
  of our 535 entries has reached it yet.
- **Where we start:** in the test model your live book's best lineup reaches 200 on about 11–13% of slates (studies 95–99;
  already 2–4 times what 26 average field lineups would). **The goal is to push that number up.** Before tonight no tested change
  had moved it more than about 3 in 100 (one reading +8, not repeated), so tonight's last studies aimed at the ceiling directly.
- **What the 200+ lineups in your fields look like** (the laptop's count over every W1–4 entry, `76f42798`): **almost 1 in 5 has
  two or more players from the QB's opponent** — a full game stack, QB + 2 + 2 — against 1.9% of our entries. It describes
  lineups after the games were played (they cluster in the games that went off, mostly in Week 1), so it does not show that
  building them helps. **Study 102 tested exactly that, building them before the games: it did not help** (section 3c).
- More lineups alone don't do it: building 41 rows instead of 26 lifts the chance that the best one reaches 200 only from 13.0%
  to 13.9% (the laptop's count). Which lineups are built matters.
- **Tonight's two ceiling studies** (sections 3b and 3c): five variations of your existing settings (study 100) and three new
  ways of building for the ceiling (study 102), each pick re-run on a fresh draw (studies 101 / 103). **Neither pick held.**
  Building every lineup on upside raised the 200+ rate on all four opponent sets, at a cost of about 12–14% of expected big
  wins; the RB version of section 2 also showed higher 200+ rates (without that cost), but at about 12–14% the rate is noisy.

## 1. The shape percentages (study 95)

Your live mix: **A1 30%** (QB + 2 receivers + a bring-back), **A2 14%** (QB + 2, no bring-back), **B 28%** (QB + 1 + a
bring-back + a pair from a second game), **C 28%** (QB + 1, no bring-back).

| Version | Pooled | Set A | Set B | Big wins | Your rule |
|---|---|---|---|---|---|
| Without A1 (the rest scaled up) | −2.0 (−6.9 to +2.8) | −1.2 | −2.8 | ×0.92 | worse on both sets |
| Without A2 | +0.1 (−3.2 to +3.5) | −0.2 | +0.4 | ×1.02 | no difference |
| Without B | −2.5 (−7.1 to +1.9) | −0.4 | −4.7 | ×0.92 | worse on both sets |
| Without C | −1.2 (−5.9 to +4.0) | −0.2 | −2.1 | ×0.93 | worse on both sets |
| A1 alone (100%) | −0.5 (−5.9 to +4.8) | +0.9 | −2.0 | ×0.98 | information (its finishes slip: a safety check fails) |
| A2 alone | +1.0 (−5.0 to +7.1) | +2.4 | −0.4 | ×1.03 | information (its finishes slip: a safety check fails) |
| B alone | −4.5 (−9.3 to +0.1) | −4.0 | −5.0 | ×0.81 | information: worse on both sets (not separable from zero) |
| C alone | −3.7 (−8.8 to +1.3) | −4.4 | −3.0 | ×0.86 | information: worse on both sets (not separable from zero) |

**The rule, written before the run:** a shape whose removal helped on both sets gets **halved** (dropped only if the gain is
clear on the pooled interval); a shape whose removal hurt on both sets gets **raised by half**; everything else **stays**; then
the shares are re-scaled to 100%. "Alone" results are information only.

**What it says, plainly: your live mix held up.** Taking out A1, B or C made the book worse on both opponent sets; taking out
A2 changed nothing; a book of only B or only C was worse on both sets; a book of only A1 or only A2 was mixed.

**The rule's suggestion: A1 39% / A2 12% / B 24% / C 24%** (the book's 26 lineups: 10 / 3 / 7 / 6, against today's 8 / 4 / 7 /
7 — two more A1, one fewer A2 and one fewer C). Only A1 moves: removing it hurt on both sets and A1 alone was not worse on both,
so the rule raises it by half; B and C hurt when removed too, but a book of only B or only C was worse as well, so the rule keeps
them; A2 stays.

**How much to trust it:** the A1 signal is weak (removing A1 cost about 2 points, with a range from −6.9 to +2.8 — the kind of
reading chance alone gives about one time in three or four), and the new mix itself was never tested. **Keeping today's mix is
just as defensible; the change is small (two lineups) and either choice is reasonable.**

**The suggested mix against today's, on a fresh draw of the same past slates (study 98, the laptop's proposal): it did not
hold.** +0.6 (−2.6 to +3.6); set A 0.0, set B +1.1; ×1.02 expected big wins — not better on both opponent sets, so by your
rule it stays on paper (study 98's READ `6d78607e`, lab `fb17beb0`; reproduced byte for byte by the laptop). Its 200+ rate
(the laptop's count): the best lineup reached 200 on 10.9% of slates against 12.7% for your mix, with the best lineup's average
177.1 vs 176.7 — no ceiling gain either. **Suggested: keep today's 30 / 14 / 28 / 28** (nothing
to change at arming). If you want the shift anyway, it is one setting (MIX_QUOTAS = A1 0.3913 / A2 0.1217 / B 0.2435 /
C 0.2435); the evidence for it is a coin flip.

## 2. Game situations (study 97)

**The research you asked for** (2018–22 and 2025; 2023–24 left out so the test stays clean):
- **The RB on the expected winner** gets about the same carries, but about **50% more goal-line carries**, nearly **twice the
  rushing touchdowns**, and **2.5× the chance of a 25-point game**; best on the favored side of a high-scoring game.
- **A favored QB does not underperform** (about 21 points vs 14 for a big underdog's QB) — but he barely moves with his own RB,
  which is why the "naked" and "trailing QB" versions were tested beside the "with his own QB" ones.
- **Trailing teams in shootouts** throw the most often and their QB–WR link is stronger, but the favored side still has the
  higher ceiling; the game total drives a QB's ceiling most.

| Version (each on your live book) | vs your book | Set A | Set B | Big wins | Your rule |
|---|---|---|---|---|---|
| RB with his QB, every C lineup (4) — a second read of 96 | −1.4 (−3.8 to +1.0) | −3.7 | +0.9 | ×0.95 | no |
| RB with his QB, only on the expected winner (by 3+) | −0.2 (−3.4 to +2.9) | +0.2 | −0.6 | ×0.97 | no |
| **… only the expected winner of a high-scoring game** | **+0.9 (−3.1 to +5.2)** | **+0.5** | **+1.3** | **×1.10** | **passes** |
| The expected winner's RB WITHOUT his QB ("naked") | +0.3 (−1.5 to +2.3) | −0.3 | +0.9 | ×1.03 | no (no change on 40% of slates) |
| The expected winner's RB with the TRAILING team's QB (QB + 1 + that RB) | −0.7 (−4.2 to +2.7) | −2.5 | +1.1 | ×1.00 | no |
| QB + 2 lineups only from high-scoring games (your idea: the shootout QB + 2 in place of today's QB + 2) | −0.7 (−4.4 to +3.0) | +0.3 | −1.8 | ×0.99 | no |
| QB + 2 lineups only from the trailing side of high-scoring games | **−5.0 (−9.4 to −0.0)** | −6.1 | −3.9 | ×0.87 | **worse** (its finishes slip too) |

Against the unconditioned RB version: the expected winner of a high-scoring game **+2.3 (−0.9 to +5.8; A +4.2, B +0.4; ×1.15) —
passes**; the expected winner alone +1.2 (A +3.9, B −1.5) — no. The naked and trailing-QB versions against the expected-winner
version: +0.5 and −0.5, neither passes (study 97's READ `53c1614f`, lab `8b9b3a9d`).

**The rule, written before the run:** an RB-with-his-QB version must beat both your book and the unconditioned RB version; the
naked and trailing-QB versions must beat your book; a QB + 2 version must beat your book; if more than one qualifies, the one
with the higher pooled gain.

**Suggested (the rule fixed before the run):** **the QB's own RB in 4 of the QB + 1 lineups, but only when his team is the
expected winner of a high-scoring game** — +0.9 against your book, better on both opponent sets, about 10% more expected big
wins; it also beats the unconditioned RB version on both sets (+2.3). **No QB + 2 version qualifies:** the shootout QB + 2 read
−0.7 (better on one set, worse on the other), and the trailing-side version was clearly worse (−5.0).

**Its 200+ rate** (descriptive, the laptop's count over study 97's books): the book's best lineup reached 200 real points on
12.7% of slates with this version against 11.8% for your book (the plain RB version 14.4%, the naked version 13.7%); the best
lineup's average was 175.6–178.2 across all versions — on the ceiling every version is within the noise.

**On your real Week-4 book** (the laptop's check of the production switch, built tonight and left off): it applied to
Buffalo, Houston and San Francisco (the expected winners of the high-scoring games), all 4 lineups got their RB, at a cost of 0.11
projected points per lineup.

**Re-run on a fresh draw of the same past slates (study 99, committed before study 97 was read): it HELD.** Both lines it had
to pass, passed again:

| Study 99 (fresh opponents and simulations, same 36 past slates) | vs | Set A | Set B | Big wins | Your rule |
|---|---|---|---|---|---|
| **RB with his QB, only the expected winner of a high-scoring game** | **your book: +3.4 (−0.4 to +7.4)** | **+5.8** | **+0.9** | **×1.18** | **passes again** |
| the same | the plain RB version: +2.8 (−0.4 to +6.2) | +2.8 | +2.8 | ×1.17 | passes again |
| RB with his QB, the expected winner (by 3+), any game (information) | your book: +1.5 (−1.7 to +4.8) | +2.8 | +0.1 | ×1.06 | passes here (did not in 97) |
| The plain RB version, every C lineup (information) | your book: +0.6 | +3.0 | −1.9 | ×1.01 | no |
| QB + 2 only from high-scoring games (information) | your book: +0.5 | +2.0 | −1.0 | ×0.99 | no |
| QB + 2 only from the trailing side of high-scoring games | your book: **−5.6 (−10.4 to −0.7)** | −2.9 | −8.3 | ×0.85 | **worse again** |

(study 99's READ `9a796eb1`, lab `79387d43`; the frozen reader of study 97 on new banks; reproduced byte for byte by the
laptop.)

**Its 200+ rate** (descriptive, the laptop's count): the book's best lineup reached 200 on **15.0%** of slates with this version
against 11.1% for your book (best-lineup average 178.9 vs 176.8); in study 97 it was 12.7% vs 11.8%. **Several other versions
were also above your book on both reads** (the expected-winner version, the plain RB version, the trailing-QB version and the
shootout QB + 2; study 97 had every version above it): at about 12%, the 200+ rate is too noisy to single any version out.

**How much to trust it now:** across the two studies the expected-winner-of-a-high-scoring-game version is ahead of your book on
all four opponent sets (+0.9 and +3.4) with 10–18% more expected big wins, and ahead of the plain RB version on all four as well.
Each single interval still crosses zero, the same 36 past slates were used both times (a fresh draw of opponents, not new games),
and the test model builds on its own projections, not Fantasy Points'. **Of the night's picks (studies 95–103) it is the only one
that held on a fresh draw** (the suggested mix, overlap 3 and the cheap-block upside version did not); whether to use it is your
call.

**Notes for reading it (the lab reviewer's 36-slate check):**
- **The "naked" version changed about 7–8 of your 26 lineups on average, and nothing at all on about half the slates** (your
  book already holds favored RBs away from their QB), so a null there says very little.
- **The trailing-side QB version** moves 11.4 of the 12 QB + 2 lineups (from 3.2) to the trailing side of a high-scoring game, at
  about **0.7 projected points per lineup**; the rest fall back when those few QBs reach their caps.
- Lineups shared with your book: QB + 2 from high-scoring games 11.4 of 26 (identical on 8% of slates); the trailing-QB RB
  version 4.7 (6%); the expected-winner RB versions 5.6 / 5.3 (never identical). Projection per lineup vs your book: expected
  winner −0.05, expected winner of a high-scoring game −0.12, RB with the trailing QB −0.17, QB + 2 from high-scoring games
  −0.11.

## 3. What it would take to use each

- **A new shape mix:** one setting at arming (MIX_QUOTAS), built and tested; any share including 0% or 100%.
- **The RB version for the expected winner of a high-scoring game (study 99 confirmed it):** its switch is built, reviewed and
  checked on your Week-4 book (Buffalo, Houston and San Francisco; all 4 lineups got their RB, −0.11 projected points per
  lineup). The lab reviewer's paper-arm update is in, and the switch is **merged at `5faf2f05`, left off**; the laptop's
  Week-4 gates at the merged state passed (00:40: with it off, your book is byte for byte today's). **Adopted on your word and
  armed for Week 5** (RB_MATE_C = 4 with RB_MATE_SCOPE = favhi; `e8a4d0a4`, FRIDAY_HEAD `b00c5e43`, the arming check passes).
- **No QB + 2 version passed,** so none was built.

## 3b. Raising the ceiling: five variations of your book (study 100) and the check of its pick (study 101)

Your note: "keep trying different variations … scores over 200 fairly regularly". Five one-setting variations of your book, each
read on its **best real lineup** (the average per slate) with the 200+ rate beside it; the rule fixed before the run picks the
largest gain that is positive on both opponent sets without costing big wins; study 101 re-runs the pick on a fresh draw.

| Version | Best lineup vs your book (points) | Set A | Set B | 200+ rate (yours: 12.3%) | Big wins: set A / set B, expected | Picked? |
|---|---|---|---|---|---|---|
| QB cap 3 (no QB in more than 3 lineups) | +0.4 (−1.1 to +2.0) | +1.1 | −0.2 | 13.2% | +3.2 / +0.2, ×1.00 | no (worse on set B) |
| **Overlap 3 (at most 3 shared players between lineups)** | **+0.7 (−1.1 to +2.5)** | **+1.0** | **+0.5** | 12.5% | +3.7 / −1.8, ×0.96 | **yes → study 101** |
| No cheap +2 block | −0.3 (−1.5 to +0.8) | −1.2 | +0.6 | 11.3% | −1.0 / +3.5, ×1.05 | no |
| Ownership cap + 10 (instead of + 15) | −0.1 (−1.3 to +1.1) | +1.0 | −1.3 | 11.6% | −0.3 / −2.4, ×0.93 | no (big wins worse on both) |
| More bring-back lineups (A1 37 / A2 7 / B 42 / C 14) | −0.3 (−2.3 to +1.7) | −0.4 | −0.2 | 11.8% | −0.7 / +0.3, ×0.99 | no |

(study 100's READ `40cec728`, lab `fd990ddf`; reproduced byte for byte by the laptop. Your book's best lineup averaged 176.8
points.)

**What it says, plainly: these five settings barely move the ceiling.** The best of them adds 0.7 points to the book's best
lineup on average, and every version's 200+ rate stays within about a point of yours (11–13%). **The pick is overlap 3**
(better best lineup on both opponent sets without costing big wins on both); study 101 re-checks it on a fresh draw. **QB cap 3
passed your big-win rule** (+1.7 overall, better on both sets: +3.2 / +0.2, ×1.00) but not the ceiling rule, and it was not
re-checked — information only.

**The pick on a fresh draw (study 101): it did NOT hold.** Overlap 3 against your book: best lineup −0.9 (A −1.3, B −0.5),
big wins −1.3 (A −1.6, B −1.0), ×0.95 — worse on both opponent sets on both measures (study 101's READ `4b847774`, lab
`36038cd6`; reproduced byte for byte by the laptop). Study 100's best simple setting was the luck of one draw (picking the best
of five flatters it). **QB cap 3's
big-win pass did not repeat either** (−0.4: A +0.3, B −1.0). **Suggested: keep your live settings.**

Nothing to arm from studies 100 / 101. Overlap 3 is planned for the Week-5 paper co-run (the lab reviewer's study 38 amendment,
pending its tests), so Sunday's real results would score it anyway, at no cost to your book.

**About the cheap +2 block (your Week-5 trial; information, not a test):** studies 100 and 101 also built your book without the
block. Without it the test model gave ×1.05 (study 100) and ×1.14 (study 101) expected big wins, with big wins −1.0 / +3.5 and
then +3.8 / +1.9 across the four opponent sets; study 53 had read the block at about 6% fewer expected big wins. That is a
5–13% cost, inside the trial's stop line (0.80× the unblocked book's expected big wins). The trial is judged on the real Week-5
results, where your book without the block is scored on paper beside it (Monday's review).

## 3c. Building for the ceiling: three new constructions (study 102) and the check of its pick (study 103)

Your note: "It sounds like you're giving up on the high scores. That's not what I want." Three new ways of building your book,
each one change, read the same way as 3b (the best real lineup, the 200+ rate beside it, the same pick rule); study 103 re-runs the
pick on a fresh draw.

| Version | Best lineup vs your book (points) | Set A | Set B | 200+ rate (yours: 12.3%) | Big wins: pooled (A / B), expected | Picked? |
|---|---|---|---|---|---|---|
| **The 8 cheap-block lineups built on each player's upside (his 85th-percentile score) instead of his average** | **+0.2 (−0.7 to +1.4)** | **+0.4** | **+0.0** | 13.2% | −0.4 (+0.1 / −1.0), ×0.97 | **yes → study 103** |
| Every lineup built on upside | −0.5 (−3.2 to +2.2) | −0.2 | −0.8 | **15.5%** (+3.2 on both sets) | **−3.5 (−3.1 / −3.9), ×0.86** | no (big wins worse on both; its finishes slip) |
| The 8 QB + 2 + bring-back lineups as full game stacks (QB + 2 + 2 from the opponent, 5 from one game) in the 4 highest-total games | **−1.7 (−3.0 to −0.3)** | −1.8 | −1.5 | 11.8% | −3.2 (−2.6 / −3.9), ×0.90 | no (worse on everything) |

(study 102's READ `3a992f7f`, lab `2ec19654`; reproduced byte for byte by the laptop. Your book's best lineup averaged
177.2 points.)

**What it says, plainly:**
- **Building every lineup on upside does what you asked for, at a price.** The best lineup reached 200 on about 3 more slates
  in 100 (15.5% vs 12.3%, on both opponent sets), but big wins fell on both sets: about 3.5 fewer slates in 100 with a big win
  and 14% fewer expected big wins, and its finishes slip (a safety check fails). That trade loses by your rule, which counts
  big wins.
- **The full game stack in the top-total games was worse on everything,** and its best-lineup loss is clear of zero
  (−1.7, −3.0 to −0.3). The 200+ lineups in your real fields look like that **after** the games; building them **before** the
  games did not help.
- **The pick, only the cheap-block lineups on upside,** was a tiny gain (+0.2 points on the best lineup, flat on big wins),
  re-checked by study 103 below.
- **What earlier tests said** matches: building on upside lost in every earlier test (study 26: −2.7, about 18% fewer expected
  big wins); the full game stack read no difference before (studies 26 and 74).

**The pick on a fresh draw (study 103): it did NOT hold.** The cheap-block lineups on upside against your book: best lineup +0.3
(A +0.7, **B −0.0**), big wins −1.0 (A +1.1, B −3.0), ×0.95 — its tiny gain in study 102 was the luck of that draw (study 103's
READ `4d0b354d`, lab `463d5050`; reproduced byte for byte by the laptop).

| Study 103 (fresh opponents and simulations, same 36 past slates) | Best lineup vs your book | Set A | Set B | 200+ rate (yours: 14.1% on this draw) | Big wins: pooled (A / B), expected |
|---|---|---|---|---|---|
| The 8 cheap-block lineups on upside (the pick) | +0.3 (−0.9 to +1.6) | +0.7 | −0.0 | 14.6% | −1.0 (+1.1 / −3.0), ×0.95 |
| Every lineup on upside | +1.1 (−1.3 to +3.7) | +1.3 | +0.8 | **16.4%** (+1.9 / +2.8) | **−3.0 (−3.3 / −2.6), ×0.88** |
| The full game stack in the top-total games | −0.8 (−2.6 to +0.9) | −0.9 | −0.7 | 12.7% | −2.5 (−1.8 / −3.1), ×0.90 |

**Building every lineup on upside repeated its trade on all four opponent sets (studies 102 and 103):** the best lineup reaches
200 about 2–3 more slates in 100, and big wins drop about 3 slates in 100 (12–14% fewer expected big wins; its finishes slip).
**By your rule, which counts big wins, it loses.** If you ever want to trade big wins for more 200+ lineups, this is the
measured price; it has no production switch (Week 6 at the earliest). (Other versions tonight also showed higher 200+ rates
without that cost — the RB version of section 2 among them — but at about 12–14% the 200+ rate is too noisy to rank on.)
**Why "built for high scores" doesn't win more** (your question this morning; descriptive, after the reads — the laptop's
tabulation of the raw rows, re-computed identically by the outside reviewer):

| | Study 102: your book | 102: every lineup on upside | Study 103: your book | 103: every lineup on upside |
|---|---|---|---|---|
| Slates whose best lineup reached 200 | 12.3% | 15.5% | 14.1% | 16.4% |
| All 200+ lineups (432 slate-banks) | 87 | 82 | 94 | 103 |
| Where a 200+ lineup finished, on average | top 1.0% | top 0.8% | top 1.0% | top 0.9% |
| Slates whose best lineup finished in the top 0.1% | 4.9% | 5.1% | 6.5% | 4.9% |

- The upside build makes about the **same number** of 200+ lineups, spread over **more** slates — so more slates "reach 200".
- A 200 in the test fields finishes around the **top 1%**; a big win needs about the **top 0.1%**.
- How often the book's best lineup reached the **top 0.1%** did not rise (5.1% vs 4.9%; 4.9% vs 6.5%), while the rest of the
  book finished lower — so big wins fell.

**The full game stack was worse again.** **Suggested: keep your live settings.**

**Using a pick:**
- **Nothing to arm from studies 102 / 103.** The full game stack's prepared switch stays unmerged and off.

**With the RB version (section 2):** the two were tested separately, so they cannot be armed together unless **study 104** —
the RB version plus the pick in one book, against the RB version alone, fixed before study 102 was read — holds them together.
It runs only if study 102 picks something and study 103 holds it. **Not run: study 103 did not hold the pick** (the condition
fixed before study 102 was read).

## What is still running this morning (information for Week 6 unless a result is clear)

1. **Study 105 — the upside dose curve (READ; information for Week 6):** on a fresh draw, against your book (200+ rate 12.0% on
   this draw), each row is the change:

   | Lineups built on upside | Best lineup reached 200 | Big wins (set A / set B), expected | Average finish |
   |---|---|---|---|
   | 13 of 26 | **+3.2 slates in 100** (+2.8 / +3.7; interval +0.5 to +6.7) | −1.7 (−2.6 / −0.7), ×0.94 | lower (check fails) |
   | 18 of 26 | −0.9 (0.0 / −1.9) | −4.5 (−5.6 / −3.4), ×0.86 | lower (check fails) |
   | 26 of 26 | +0.7 (−0.9 / +2.3) | −3.4 (−6.1 / −0.8), ×0.90 | lower (check fails) |

   **Every dose cost big wins on both opponent sets; the 200+ gain jumps around** (+3 at 13 lineups, −1 at 18, +1 at all 26;
   the same all-26 version read +3.2 and +2.3 in studies 102 / 103), so there is no "sweet spot" that buys 200+ lineups without
   giving up big wins. Read on your book before the RB version (study 105's READ `efbea1ce`, lab `6ab0b595`).
2. **Study 106 — a projection floor** (your "no player with a projected score less than 8"): **READ — worse; keep your book
   as is.** A floor of 8 against your armed book (with the RB version): −2.7 slates in 100 with a big win (−2.7 on set A, −2.7 on
   set B; interval −7.7 to +2.0), 12% fewer expected big wins, the average finish lower (check fails); its 200+ rate also fell
   (13.7% → 12.0%). So the fresh-draw check (study 107) and **your per-position floors (study 108) are not run**: they waited on a
   floor that helped (study 106's READ `0a75e37c`, lab `960c320c`). Before the run, the floor of 10 was dropped: on our
   model's projections it left almost no cheap players, so the cheap block came out empty (on that scale it acts like
   production's 12). **A live floor is one existing setting and uses Fantasy Points' projections** (the ones
   your book is built on); the test uses our model's (the only history it has), so a passing floor's number transfers only
   approximately. On your real Week-4 book an FP floor of 8 changes 3 of 26 lineups and 10 changes 23 (the laptop's check). A
   floor of 12 is not tested: with the cheap block on, production refuses it (it removes every cheap-block player).
3. **Study 109 — a recency fade** (your "2 point reduction in the projection when the players last game was twice the
   average"): **READ — worse; keep your book as is.** Against your armed book (with the RB version), each was below on both
   opponent sets:
   - **−2 points at twice the average:** −4.7 slates in 100 with a big win (−5.7 / −3.7), 20% fewer expected big wins, the
     average finish lower (check fails);
   - **the same at 1.6×:** −5.2 (−4.0 / −6.3), 21% fewer expected big wins, check fails;
   - **at most one "hot" player per lineup** (added this morning at your "Add both today"; no change to the projections): −1.8
     (−2.5 / −1.2), 10% fewer expected big wins, the average finish within the check.
   - The 200+ rate barely moved in any of them. Nothing passed, so the fresh-draw check (109b) is not run (study 109's READ
     `169cc082`, lab `fb004daf`). In the test model the players coming off a big game are still worth their projection; the
     pros' habit of fading them did not translate into more big wins here.
4. **Study 110 — rules from your real Weeks 1–4 fields** (the ideas page you queued): no low-owned player at all; the QB from
   one of the slate's three highest-total games; the cheap block only on popular cheap players; no QB with his own defense and
   at least $49,500 of salary. **Added this morning ("Add both today"):** at most 4 of a lineup's 8 players from the top tenth by
   value. A pick is re-checked on a fresh draw (study 111).
5. **Study 112 — usage floors** (your minimum rush attempts, pass attempts, targets, touchdowns and red-zone targets): one floor
   per version, each from this season's games before the slate only; a pick is re-checked on a fresh draw (study 113). The
   levels were set by a rule written down before any result: each floor changes about 8–15 of your 26 lineups. **That gives at
   least 13 carries a game for running backs, 32 pass attempts for QBs and 4.5 targets for receivers and TEs.** **Touchdowns and
   red-zone targets could not be tested this way:** a player with no touchdown in his recent games averages zero, so any
   touchdown floor removes all of them at once and changes about 22 of 26 lineups; the red-zone floor is similar (16 lineups at
   its lowest step). Both were dropped before the run.
6. **Last, as you asked (study 114):** "Did we try what you had planned of removing one rule at a time to see if it was really
   helpful? That in my opinion should be the last thing we do after we've tried the other experiments." The shapes were done
   this way (study 95: removing A1, B or C hurt; A2 changed nothing). Study 114 removes each live **rule** in turn from your
   full armed book: the 35% cap with the ownership limit (as one), the one-TE limit, the one-low-owned limit, the cheap block,
   one receiver per team, and the RB version. A removal is suggested only if your book does better without it on both
   opponent sets; with six removals one or two can pass by chance, so a suggested removal is re-checked on a fresh draw (study
   114b) before it reaches you. **Only two can be switched off for tonight as things stand** (the cheap block, the RB version);
   the others are tied together in the arming script, so removing one of them would wait for Week 6. Every study ends by about
   17:30, **before your 18:00 final arm.**
7. **Your question "77, 79 and 81 all looked promising. Do you think any could be adopted?" (the laptop's answer, checked
   against the ledger):** 79 is already live, as one receiver per team (study 93, +2.0). 77 (the QB alone, +1.8 at first) and
   81 (no $5,000+ TE, +4.7 as one of about 35 side comparisons) failed their re-reads: 77 read −1.9, −2.0 and −0.2 afterwards;
   81 read −1.2 on fresh opponents. Neither is adoptable.

## 4. The rest of last evening (for the record)

- **One receiver per team in the QB + 1 lineups (study 93): armed** (+2.0, better on both sets; your "Live W5 if built").
- **The RB stack mate (study 94) +2.0 without that rule → study 96 with it −0.5:** the two did not add up.
- **A defense with its own RB (study 94): −1.0,** paper only.
- **Your "correlate data points" question:** DVOA-style defense adjustment is already in our model (adds ~0); receiver vs. man /
  zone coverage and route-share bounce-back showed nothing; the crowd's ownership beat OUR old projections in Weeks 1–2 but adds
  nothing against Fantasy Points' (why switching to FP and the ownership limit pointed the right way).

*Every number above is quoted from the studies' frozen readers (each reproduced byte for byte by the laptop); the documents
behind them: the preregistrations and the study system's Addenda for studies 93–103.*
