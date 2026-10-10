# Week 5, Saturday morning: the shape percentages and the game-situation rules (2026-10-10)

**For:** Erich, first thing Saturday, before the 10:28 arming. Written by the outside reviewer; the lab reviewer read every
study and the laptop re-ran every read with identical output. **Your rules last night:** no questions to you overnight; "If
something is successful, we'll discuss in the morning how we want to use it."

## The short version

- **Shape percentages (study 95):** your mix held up — removing A1, B or C was worse on both opponent sets. The rule fixed
  beforehand suggests a small shift: **A1 39% / A2 12% / B 24% / C 24%** (two more QB + 2 + bring-back lineups), on a weak
  signal; keeping today's 30 / 14 / 28 / 28 is just as defensible.
- **Game situations (study 97):** [FILLED FROM STUDY 97'S READ BY ITS §3 RULE, FIXED BEFORE IT]
- **The RB stack mate, unconditioned (study 96): paper only.** On top of the one-receiver-per-team rule it read −0.5 (worse on
  both opponent sets), although every lineup got its RB. It stays off (RB_MATE_C = 0) unless you choose a version below.
- **Already armed for Week 5 (your decisions):** Fantasy Points' projections, the winners' shape mix, the cheap +2 block, the
  35% cap with the ownership limit (+ 15), at most one TE and one player under 3% per lineup, and one receiver per team in the
  QB + 1 lineups.

**How to read the numbers:** "+2.0" means about 2 more slates in 100 with a big win, on the test model (36 past slates of
2023–24, scored on their real results, against two separate random sets of opponents, "A" and "B"). **Your rule** for a change:
better on both opponent sets, without losing more than 20% of expected big wins. **Under no real effect a change passes that
rule about one time in three or four.** Tonight's two studies make 19 such comparisons (95: 8, 97: 11), all on the same 36
slates as studies 89–96 — so about five to six passes are expected by chance alone, so a pass is a candidate to try, not
proof. **The test model builds lineups from its own simulated projections; your book uses Fantasy Points', so a gain there may
not carry over** (studies 91 and 92 showed both directions). The laptop's Week-4 check shows what a change does to your real
book.

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

**The suggested mix against today's, on a fresh draw of the same past slates (study 98, the laptop's proposal):** [ ] — a
check against a lucky draw, not new games. Arming any mix is one setting
(MIX_QUOTAS = A1 0.3913 / A2 0.1217 / B 0.2435 / C 0.2435).

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
| RB with his QB, every C lineup (4) — a second read of 96 | [ ] | [ ] | [ ] | [ ] | [ ] |
| RB with his QB, only on the expected winner (by 3+) | [ ] | [ ] | [ ] | [ ] | [ ] |
| … only the expected winner of a high-scoring game | [ ] | [ ] | [ ] | [ ] | [ ] |
| The expected winner's RB WITHOUT his QB ("naked") | [ ] | [ ] | [ ] | [ ] | [ ] |
| The expected winner's RB with the TRAILING team's QB (QB + 1 + that RB) | [ ] | [ ] | [ ] | [ ] | [ ] |
| QB + 2 lineups only from high-scoring games (your idea: the shootout QB + 2 in place of today's QB + 2) | [ ] | [ ] | [ ] | [ ] | [ ] |
| QB + 2 lineups only from the trailing side of high-scoring games | [ ] | [ ] | [ ] | [ ] | [ ] |
(The expected-winner versions are also compared with the unconditioned RB version: [ ].)

**The rule, written before the run:** an RB-with-his-QB version must beat both your book and the unconditioned RB version; the
naked and trailing-QB versions must beat your book; a QB + 2 version must beat your book; if more than one qualifies, the one
with the higher pooled gain.

**Suggested:** [ ]

**Each pick re-run on a fresh draw of the same past slates (study 99, committed before study 97 was read):** [ ] — a pick
counts as "held" only if it passes the same rule again.

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
- **A game-situation version (RB or QB + 2):** if one passes, its switch is built overnight and left OFF. Using it needs one
  setting, the laptop's Week-4 check, and a paper-arm update from the lab reviewer (without it, the integrity check refuses the
  new switch). A version that fails is not built.
- **An RB version and a QB + 2 version together:** not allowed by the switches tonight — study 97 read them separately, and
  separately-read rules have not added up before (studies 93 + 94; study 83's combination −1.9). If you want both, one goes live
  and the other on paper, or a combined test (about 40 minutes) if the clock allows before 10:28.

## 4. The rest of last evening (for the record)

- **One receiver per team in the QB + 1 lineups (study 93): armed** (+2.0, better on both sets; your "Live W5 if built").
- **The RB stack mate (study 94) +2.0 without that rule → study 96 with it −0.5:** the two did not add up.
- **A defense with its own RB (study 94): −1.0,** paper only.
- **Your "correlate data points" question:** DVOA-style defense adjustment is already in our model (adds ~0); receiver vs. man /
  zone coverage and route-share bounce-back showed nothing; the crowd's ownership beat OUR old projections in Weeks 1–2 but adds
  nothing against Fantasy Points' (why switching to FP and the ownership limit pointed the right way).

*Every number above is quoted from the studies' frozen readers; the documents behind them: the preregistrations and the study
system's Addenda for studies 93–97.*
