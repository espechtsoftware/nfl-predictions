# Week 5, Saturday morning: the shape percentages and the game-situation rules (2026-10-10)

**For:** Erich, first thing Saturday, before the 10:28 arming. Written by the outside reviewer; the lab reviewer read every
study and the laptop re-ran every read with identical output. **Your rules last night:** no questions to you overnight; "If
something is successful, we'll discuss in the morning how we want to use it."

## The short version

- **Shape percentages (study 95):** [FILLED FROM STUDY 95'S READ BY THE RULE FIXED BEFORE IT — `92108ea0`]
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
| Without A1 (the rest scaled up) | [ ] | [ ] | [ ] | [ ] | [ ] |
| Without A2 | [ ] | [ ] | [ ] | [ ] | [ ] |
| Without B | [ ] | [ ] | [ ] | [ ] | [ ] |
| Without C | [ ] | [ ] | [ ] | [ ] | [ ] |
| A1 alone (100%) | [ ] | [ ] | [ ] | [ ] | information |
| A2 alone | [ ] | [ ] | [ ] | [ ] | information |
| B alone | [ ] | [ ] | [ ] | [ ] | information |
| C alone | [ ] | [ ] | [ ] | [ ] | information |

**The rule, written before the run:** a shape whose removal helped on both sets gets **halved** (dropped only if the gain is
clear on the pooled interval); a shape whose removal hurt on both sets gets **raised by half**; everything else **stays**; then
the shares are re-scaled to 100%. "Alone" results are information only.

**Suggested mix:** [ ] — **on your real Week-4 book** (the laptop's builds): [ ]. Arming any mix is one setting (MIX_QUOTAS).

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
| QB + 2 lineups only from high-scoring games | [ ] | [ ] | [ ] | [ ] | [ ] |
| QB + 2 lineups only from the trailing side of high-scoring games | [ ] | [ ] | [ ] | [ ] | [ ] |
(The expected-winner versions are also compared with the unconditioned RB version: [ ].)

**The rule, written before the run:** an RB-with-his-QB version must beat both your book and the unconditioned RB version; the
naked and trailing-QB versions must beat your book; a QB + 2 version must beat your book; if more than one qualifies, the one
with the higher pooled gain.

**Suggested:** [ ]

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

## 4. The rest of last evening (for the record)

- **One receiver per team in the QB + 1 lineups (study 93): armed** (+2.0, better on both sets; your "Live W5 if built").
- **The RB stack mate (study 94) +2.0 without that rule → study 96 with it −0.5:** the two did not add up.
- **A defense with its own RB (study 94): −1.0,** paper only.
- **Your "correlate data points" question:** DVOA-style defense adjustment is already in our model (adds ~0); receiver vs. man /
  zone coverage and route-share bounce-back showed nothing; the crowd's ownership beat OUR old projections in Weeks 1–2 but adds
  nothing against Fantasy Points' (why switching to FP and the ownership limit pointed the right way).

*Every number above is quoted from the studies' frozen readers; the documents behind them: the preregistrations and the study
system's Addenda for studies 93–97.*
