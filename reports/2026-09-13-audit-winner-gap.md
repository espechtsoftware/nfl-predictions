# The gap to the Millionaire winner, week by week (2023–2024, 35 matched weeks)

Source: `milly-winners-2019-2023-2024.csv` (winner rosters, summed points) vs the PREREG-096 bank-960 books (DEMAX K80,
its first 30, and the 800-candidate pool oracle) on the same slates. Data: `reports/2026-09-13-audit-winner-gap.csv`.

| quantity | value |
|---|---|
| Millionaire winner | mean 230.4, median 232.5, min 178.3, max 296.4 |
| our K80 best | mean 181.8 (gap 48.6; best week −11.6) |
| our K30 best | mean 171.9 (gap 58.5) |
| our 800-pool oracle | mean 194.7 (gap 35.7) |
| weeks our K80 best ≥ winner | 1 of 35 (2024 w9: winner 185, ours 197) |
| weeks our pool held a winner-beating lineup | 1 of 35; within 10 points: 2 |
| weeks the winner scored ≤ 220 | 10 of 35 (ours in those weeks: 25–60 below, except 2024 w9) |
| corr(winner score, our best) | 0.70 (0.77 vs the pool oracle) |

2025 winners (17 weeks): mean 236.9, median 239.3, ≤220 in 4 weeks, ≤230 in 5; 4.2 sub-10%-owned players per winning
lineup, QB ownership 8.7% on average, stack size 3.2.

Reading: the winner's score moves with the week (corr 0.7), so "220" is not the target — the target is the field's
maximum that week, which ranged 178–296. Our entered book sits ~49 points below it on average and our whole candidate
pool ~36; the observed win rate is one week in 35 at K80. Today's 216 in a 59-point-game week is a $30 finish; in 10 of
these 35 weeks the same 216 is a top-10 finish or the win. No lever in the ledger moves the book more than ~2 points and
the 3200 dose moves the pool oracle ~8; the gap is 35–50. A win-rate objective (finish vs the field, ownership-aware),
not a points objective, is the only framing under which the remaining levers are even measured correctly.
