# Study 72 closed: a stack from a game outside the top four is already in the live book (2026-10-08)

**For:** the operator's question (study list 42(d)). Written by the reviewer, 10-08 evening.

**Decision (the operator, 10-08):** "Close it, track Monday." Study 72 was not frozen and never scored. Banks 1629–1634
and seed 20261117 stay unused.

## The question
- **His words, 10-08:** "Try picking a game that isn't one of the top, you know, two or three or four games and just doing
  a stack and just like one lineup of that or something."
- **Tonight:** "Try your idea of one stack from a game outside the top few … It has never been tested as a forced single
  lineup."

## What the outcome-blind census found
- **Source:** study 48's harness, his live book with the cheap +2 block (LIVE_CB), Rev6, all 53 slate-banks of 2022–24
  on bank 1406 (never a decision bank).
  - Mechanics only: no point, percentile or field was read.
  - Lab `production/s72-otherscript-20261008` @ `2ff5982`: `results/s72/CENSUS_s72_probe.txt` `4cf1714a…`, the raw
    mechanics rows `657c222a…`.
  - Code `82c50ce`: it was run on the identical working tree just before that commit.
- Games are ranked by game total (ties by game id), over the games with a QB in the pool. A slate has 11 games at the
  median (8 at the fewest).

| Measure | Value |
|---|---|
| Rows of 26 whose QB's game ranks 5th or lower | **9.2** on average |
| … of them in positions read by a big contest (book indices 0–21) | **7.5** |
| Slate-banks with none in the big seats | 1 of 53 |
| The Millionaire's two entries: at least one such row / both | 66% / 21% |
| The Millionaire's 2nd entry already such a row | 32% |
| The last-built row (the proposed forced row) already such a row | 43% (5th or lower); 72% (3rd or lower) |

## What this means
- **One forced lineup would add nothing new.** The live book already plays games outside the top four in about a third
  of its lineups, most of them in the big contests. The QB cap (5 rows per QB) and the winners' mix spread the QBs.
- **The narrower question is low-power.** "Should the Millionaire's 2nd entry always be one?" would change that seat on
  68% of slate-banks. That is a one-seat change: a test could rule out only a large effect, and its 2022 sign would be
  close to a coin flip.
- **Two design problems were caught before any scored bank:**
  - The first design dealt the forced row where it was built (book index 24 under Rev6), which only non-big supersats
    read, so it could never move P(≥ 1 big). The laptop and the outside reviewer caught it.
  - The census then showed the forced row usually already was such a lineup.

## What happens instead
- **Monday's tracking line** (descriptive, gates nothing). The outside reviewer proposes the format and the laptop
  reviews it. Each week, our entered book's rows stacking a QB from a game ranked 5th or lower by the T-70 game total:
  - the count, and how many sit in big seats;
  - their points and finishes in the real fields;
  - beside the field's same rows.
