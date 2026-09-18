# Adding variation without losing points, and what actually protects against an injury (2026-09-18)

The operator asked for ways to vary entries that do not cost points, motivated by "I don't want an injury to wreck my
day". Four ideas were tested on the same 65 historical slates (PREREG-097 bank 970, D3200 K80 books) scored on
realized DK points. **Exploratory: these books were already read for PREREG-100, so nothing here is a preregistered
result and none of it is adopted.**

## 1. General exposure caps — cost points, and do not fix the injury problem

Walk the book in rank order, skip a lineup that would push any player above the cap.

| block of 23 | max exposure | deepest rank used | mean best | ≥180 | worst-case single scratch | loss |
|---|---:|---:|---:|---:|---:|---:|
| no cap | 54 % | 23 | 171.9 | 34 % | 154.6 | 17.3 |
| 50 % | 43 % | 28 | 170.2 | 31 % | 153.8 | 16.4 |
| 40 % | 38 % | 32 | 170.4 | 32 % | 153.0 | 17.4 |

Caps below 40 % are unreachable from an 80-lineup book on a third of slates. **The key negative:** the worst-case loss
from a scratch is essentially unchanged (17.3 → 17.4). Capping exposure spreads a player across fewer lineups, but the
damage comes from the scratch hitting *the best lineup*, and that lineup usually still contains him. A general cap buys
cosmetic diversification at about 1.5 points.

(An earlier run appeared to show a 30 % cap improving results; that was an artefact — the cap was unreachable on 21 of
65 slates and those slates dropped out of the average. Corrected above by reporting reachability.)

## 2. Core plus a one-player swap — tested at the operator's suggestion, far too weak

Reported in `reports/2026-09-18-satellite-entry-allocation-question.md`: a block of the best lineup plus nine variants
that swap one player reaches 180 in 7.7 % of slates against 24.6 % for the book's own ranks 1–10, and the book's block
is 30 points better on the mean best. Swapping the expensive slot is no better than the cheap one. The selector already
discards near-duplicates (average number of book lineups one player away from rank 1: **0.0**), and the record says it
is right to.

## 3. Capping only injury-flagged players — the one that looks free

Cap only players flagged **Questionable + did-not-practise, Questionable + limited, or Doubtful** — the cells PREREG-100
measured at −5.9, −2.9 and −11.8 points against projection, with zero-point rates of 47 %, 25 % and 99 %.

| block of 30 | max flagged exposure | lineups holding a flag | deepest rank | mean best | ≥180 | ≥190 |
|---|---:|---:|---:|---:|---:|---:|
| no cap | 16 % | 43 % | 30 | 173.5 | 37 % | 25 % |
| 20 % | 15 % | 42 % | 31 | 173.5 | 37 % | 25 % |
| 10 % | 9 % | 36 % | 35 | **174.7** | 38 % | 25 % |

Paired on matched slates, excluding flagged players entirely:

| block | matched slates | uncapped mean best | no-flagged mean best | paired delta | 95 % interval | better / worse |
|---|---:|---:|---:|---:|---|---|
| 23 | 61 | 172.4 | 173.9 | **+1.50** | [−1.97, +5.26] | 14 / 14 |
| 30 | 53 | 171.7 | 174.2 | **+2.45** | [−0.79, +6.11] | 16 / 10 |

**Reading:** excluding the flagged cells is free at worst and mildly positive at best, while cutting the share of
lineups carrying an injury-flagged player from 43 % to 0 % (or to 36 % at a 10 % cap). The intervals cross zero and the
win/loss counts are close, so this is *not* a demonstrated points gain — the honest claim is **meaningful risk
reduction at no measurable cost**. It reaches deeper into the book (rank 42–50 of 80), which is where the extra
variation comes from.

This is the same direction as PREREG-100's player-level finding and stronger than its book-level demotion test, because
excluding is stricter than demoting.

## 4. What actually protects the day

The evidence says injury protection comes from *who is in the lineups*, not from how the lineups are spread:

- **Before lock:** the scratch protocol (remove only players DraftKings marks OUT/IR or the official inactives name)
  plus the vetting demotion already in the path. Strengthening demotion to exclusion for the three flagged cells is the
  candidate change, on the evidence above.
- **Not from exposure caps:** they do not reduce the worst-case loss.
- **Not from near-duplicate variants:** they share the core that carries the risk.

## Proposed next step (not a Week-2 change)

Preregister the exclusion rule properly: arms = vet-and-demote (current), exclude Q_dnp + doubtful, exclude those plus
Q_limited; primary = the ledger's K30 proxy on fresh banks; secondary = share of entered lineups holding a flagged
player, and realized outcome after a confirmed in-game injury. It is a rule that touches the entered book, so it needs
the 72-slate test before it is used, per the standing rule. For Week 2 the existing demotion stays.
