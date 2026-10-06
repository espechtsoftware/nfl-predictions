# Week 5: your decisions (draft for Friday)

2026-10-05, written for you. Four decisions. Each is reversible, and none is armed without your yes. The contest
plan's dollars are in your private draft, not here (this repository is public).

## The short version

| # | Decision | My recommendation |
|---|---|---|
| 1 | The lineup shape: WS, the shape-mix portfolio (MIX), or today's | **WS**: the only change that passed its test |
| 2 | Fantasy Points' projections instead of ours | **Yes** (you decided this in principle; the Week-4 check worked) |
| 3 | The lab-code update both of these need | **Yes**: it changes nothing when they're off (proven below) |
| 4 | The Week-5 contest plan (draft A: 21 entries in shallow-line qualifiers) | **Yes, or your edits** |

## 1. The lineup shape

**What we tested.** Study 18 rebuilt the book on 53 practice slates (2022–24), against your Week-5 draft plan's cash
lines, in three ways:

| Version | What every lineup looks like | Tickets vs today's | Average finish | Slates with no ticket |
|---|---|---|---|---|
| Today's | QB + 2 pass catchers + an opponent bring-back, always | — (737 tickets) | — | 10% |
| **WS** | QB + 1 pass catcher, a player from each team of a second game, at most 3 from the QB's game, rarely a bring-back | **+42% (1,047)**, every season better | **up ~3 points** | 15% |
| MIX | the winners' mix: 30 / 14 / 28 / 28% of four shapes | +16% (856), not conclusive | up ~1 point | 15% |

- **WS passed** the frozen test, which was written before any results were seen. That is the bar we use.
- **The cost:** a wider swing. A few more slates where the whole book wins nothing, and the worst slates are a little
  worse.
- **MIX** is the "mix of shapes like the winners" you asked for. It moved the right way but was not conclusive.
- **On your "not one strategy everywhere":** WS is one shape, but a much looser one than today's. It spreads the book
  over about 4.8 games, against 4.3 today, and is less tied to one game. A further idea, by contest type (WS for
  qualifiers, today's tighter stack for any Millionaire entries), is on the study list as item 23.

## 2. Fantasy Points' projections

- **Your decision (10-05):** use FP's instead of ours, unless ours or a blend beats them.
- **Week 4, the only week with FP data:** FP was a little more accurate than ours (average miss 5.47 vs 5.56 points).
  A 50/50 blend tied FP.
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

## 4. The Week-5 contest plan

- **Draft A** (sent to you privately) follows your mix: $555, $333 and Millionaire qualifiers, at last week's budget.
- **It uses the shallow-line versions:** 9–22% of the field paid. At our current level they lose about half as much
  per dollar as the 1%-line ones.
- **All the testing above used this plan's cash lines.**
- **The counts are yours.**

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

- **The combination is untested as a whole.** Studies 17 and 18 ran on OUR simulated projections, without the
  ownership adjustment. "WS (or MIX) + the ownership adjustment + FP projections" as a combination is untested except
  by the one-week Week-4 replay. There is no FP data for 2022–24, so a full test of the combination is not possible.
- **Book size differs.** With 21 entries the build makes a 17-row book; the study dealt from 105 rows. The caps are
  the same shares, so it should carry over, but it is not identical.

## If you say yes: how it runs and how we undo it

- **Arming:** the Saturday arming line adds
  `UNION_MAIN=mix UNION_MIX_PORTFOLIO=ws UNION_PROJ_SOURCE=fp`, with the lab pin moved to the new code. The arming
  banner prints the choice, so a missed line can't silently pick the wrong arm.
- **Safety nets:**
  - if WS can't fill the book, the build falls back loudly to today's shape;
  - if FP's capture fails a check, it falls back loudly to our projections;
  - every audit and Sunday's replacement of ruled-out players already understand the new shapes.
- **Undo:** remove those three settings and move the pin back. Today's build is unchanged.
- **Monday:** the entered book against a paper rebuild of today's book on the same slate, plus the shape you actually
  entered and the ours / FP / blend accuracy.
