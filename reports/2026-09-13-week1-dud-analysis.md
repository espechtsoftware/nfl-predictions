# Week-1 dud analysis: the two weak players per lineup, and whether the data saw them coming (2026-09-13 evening)

Operator's brief: most players did well but each lineup carried about two that did not; analyze those, check whether the
data suggested they would not do well, how often they score high, and whether their last high game was borrowed from a
depth-chart injury. Winners' analysis follows Monday when standings are available.

Data: today's points from ESPN box scores (late games were in their final minutes at capture; DraftKings' exact scoring
may differ by a point or two), the two entered-book candidates (v4b = scratches only; v6b = the proven-scorer rule),
the 2024–2025 game log for every entered player from the point-in-time panel, the injury reports 2021–2025, and the
PREREG-096 historical books. Files: `reports/week1-duds/`.

## 1. Today's book, scored

| candidate file | best lineup | mean | lineups ≥ 180 | ≥ 200 |
|---|---:|---:|---:|---:|
| v4b (scratch swaps only) | ~210 | 143 | 7 | 2 |
| v6b (proven-scorer rule applied) | ~190 | 143 | 6 | 0 |

The best v4b lineup: Gibbs 37.6, Jalen Coker 36.8, Bryce Young 35.4, Swift 35.4, Jefferson 21.3, Jaguars 15.0, Hockenson
13.6, McMillan 11.5, Aaron Jones 3.5. Its second: Henry 38.3, Coker 36.8, Young 35.4, Olave 31.2, Hubbard 23.7, Jaguars
15.0, Garrett Wilson 13.9, McMillan 11.5, Loveland 0.0. **Jalen Coker — one big game in 33 (3%), the exact profile the
proven-scorer rule removes — was the day's decisive boom**, which is why v6b tops out 20 points lower. Both books' best
lineups still carry a zero or near-zero (Jones 3.5, Loveland 0.0): a 210 with a dud replaced by an average game is a 225.

## 2. The recurring duds

Bottom-two players per lineup, v4b (v6b is the same list minus Lloyd, Jones and Dulcich, plus Barkley and Smith):

| player | salary | today | dud in | 2024–25 games | big games (rate) | injury-driven | last big | pre-lock flags |
|---|---:|---:|---|---:|---|---|---|---|
| Ja'Marr Chase, CIN WR | 7,800 | 3.2 | 20 of 22 | 33 | 20 (61%) | 0 | 2025-w18 | did not practice Friday (knee), no game designation, props posted |
| Tre Tucker, LV WR | 4,000 | 4.7 | 9 of 13 | 34 | 2 (6%) | 0 | 2025-w3 | none |
| Quentin Johnston, LAC WR | 4,700 | 3.7 | 6 of 6 | 34 | 6 (18%) | 0 | 2025-w16 | none |
| Kyler Murray, MIN QB | 5,500 | 0.6 | 6 of 6 | 34 | 5 (15%) | 0 | 2024-w18 | none (3 of 5 passing, left the game) |
| Chris Godwin, TB WR | 5,200 | 8.3 | 6 of 13 | 33 | 4 (12%) | 0 | 2025-w17 | none |
| Marvin Harrison Jr., ARI WR | 5,000 | 4.3 | 5 of 9 | 34 | 3 (9%) | 0 | 2025-w9 | none |
| MarShawn Lloyd, GB RB | 4,800 | 4.0 | 5 of 5 | 33 | 0 | – | none | none |
| Colston Loveland, CHI TE | 5,300 | 0.0 | 5 of 5 | 17 | 3 (18%) | 0 | 2025-w18 | none (0 catches in a 59-point game) |
| Browns DST | 2,100 | 2.0 | 5 of 5 | | | | | |
| Aaron Jones, MIN RB | 5,300 | 3.5 | 5 of 8 | 33 | 3 (9%) | 0 | 2024-w12 | none |
| Tony Pollard, TEN RB | 5,600 | 4.4 | 5 of 6 | 34 | 4 (12%) | 0 | 2025-w15 | none |
| DK Metcalf, PIT WR | 5,400 | 8.0 | 4 of 4 | 33 | 4 (12%) | 0 | 2025-w14 | none |
| Greg Dulcich, MIA TE | 3,500 | 3.8 | 4 of 4 | 34 | 1 (3%) | 0 | 2025-w17 | none |
| Harold Fannin Jr., CLE TE | 4,200 | 4.1 | 4 of 4 | 17 | 4 (24%) | 0 | 2025-w16 | none |

"Injury-driven" = the big game came in a week when a higher-scoring same-team, same-position teammate was absent. For
these players the answer is no: none of their big games were borrowed from an injury. Among all 2,901 big games in the
2020–2024 panel, 6.4% were injury-driven; the depth-chart story is real but small.

Three groups:

1. **A stud with a practice red flag (Chase, 22 lineups).** The data did not say he would flop on talent (61% big-game
   rate); the practice report did, mildly. Historically, established players who did not practice Friday, carried no game
   designation and then played delivered 82% of their trailing mean with a **36% flop rate versus 24% for healthy
   players**, and the same 24% big-game rate. Did-not-practice *plus* Questionable is worse: 69% of trailing mean, 13% big,
   37% flop. Our vetting scored Chase "soft" because the market kept his line. Twenty-two of 80 lineups on a player with a
   1.5× flop rate is a risk-management failure, not a modeling one.
2. **Healthy, unflagged players who simply had nothing (Murray, Loveland, Pollard, Metcalf, Johnston).** No pre-lock
   signal in any table we have. Murray left the game; Loveland had two targets in a 59-point game.
3. **Low-frequency boomers at $4,000–5,300 (Tucker 6%, Harrison 9%, Jones 9%, Godwin 12%, Dulcich 3%, Lloyd 0%).** The
   data does say they rarely score high. It said the same about Coker (3%), who scored 36.8 and made both 200+ lineups.

## 3. Would removing the low-frequency players have helped? Historically, no

Unproven = no big game (QB 25+, RB/WR 20+, TE 15+) in the trailing year. Share of skill slots held by unproven players:
**perfect lineups 18%** (only 14% of perfect lineups are entirely proven; 47% of their ≤$4,000 players are unproven),
historical K80 books 16% (1.3 per lineup), today's v4b 9%, v6b 3%. The book already carries fewer unproven players than
the perfect lineups do. Rule tests on the 72 historical books (K30 realized best vs the plain first 30):

| rule | K30 delta | lineups passing per 80 | 220-weeks |
|---|---:|---:|---|
| every player proven (any big game) | −9.8 | 16 | 4 → 4 |
| every player proven, injury-driven booms excluded | −14.6 | 12 | 4 → 4 |
| at most one unproven player | −0.9 | 50 | 4 → 5 |
| at most two unproven players | +0.2 | 72 | 4 → 4 |

The strict rule is disastrous because it discards four of five lineups; the soft rules are flat. Low-frequency boomers are
where the cheap upside lives (Coker today, 18% of every perfect lineup); the problem is not their presence but that a
lineup needs the right two of them.

## 4. What is actionable from today

- **Practice-status exposure cap (new, evidence-backed).** Treat "did not practice Friday" as material in vetting
  regardless of posted props, and cap any such player at ~10% of the book; treat DNP + Questionable as a hard demotion.
  Expected value: small on average (it trades a 24%-big-rate player for another 24%-big-rate player) but it removes the
  correlated flop risk that took 22 of 80 lineups down today. To be implemented in `week1_vet_book.py` and tested on the
  historical books before Week 2.
- **Exposure caps by big-game rate, not exclusion.** Players with a trailing big-game rate under 10% should not exceed
  ~15% of the book; the same player can still appear (Coker) without concentrating the book on him (Tucker in 13–16
  lineups). A construction-level change; test as a lab arm, not a filter.
- **Winners' analysis (Monday).** Pull the Millionaire's top 100 lineups from the standings export, profile every player
  the same way (big-game rate, practice status, salary), and compare against §2–3 directly. The question the operator is
  really asking — do winners' cheap booms look different in advance from ours — is answerable with that file.
