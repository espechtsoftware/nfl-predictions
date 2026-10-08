# Week 4's "necessary" players, and why today's system would still have missed them

2026-10-08 evening, the outside reviewer, written for you. Descriptive, plus the tests started tonight. It changes
nothing on Sunday unless a test passes and you choose it at Saturday's arming.

**Your questions (10-08):** "It seems that the necessary players were relatively low owned. Would our system today have
picked them?", then "I find this somewhat concerning. Is there a test we can do immediately to try to fix this for this
week?", and "Please do whatever testing is needed without input from me."

## The short answers

1. **The players Week 4's top lineups needed:**

   | Player | Points | Owned | Top 10 lineups | Top 95 lineups ($500+) |
   |---|---|---|---|---|
   | Nico Collins | 33.8 | 12% | 9 | 92% |
   | CeeDee Lamb | 44.3 | 10% | 9 | 86% |
   | T.J. Hockenson | 27.9 | 16% | 6 | 66% |
   | C.J. Stroud | 26.1 | 6% | 5 | 65% |

   Only Stroud was truly low-owned. The winners' edge was the combination: Stroud, Collins and Lamb from the
   Texans–Cowboys game (the slate's third-highest total).
2. **Today's settings rebuilt on Week 4 would have missed it.**
   - The 26 lineups held:
     - Hockenson in 13 (the maximum);
     - Stroud + Collins in 2;
     - Lamb in 0;
     - Collins + Lamb together in 0.
   - The best lineup scored 181 (about 1,900th place, worth $70). None reached the $500 places.
3. **The miss is structural.**
   - Our two Stroud–Collins lineups held no Dallas receiver, or only the cheapest one: Ryan Flournoy, boosted by the
     cheap +2.
   - The builder maximises Fantasy Points' projection per dollar. Lamb ($7,800, 18.1 projected) was only the 24th-best
     value among receivers.
4. **The quick fix doesn't work.**
   - I gave every team's top-salaried receiver +2, then +3, then +4 on the 8 block lineups. Lamb still appeared in 0 of
     26.
   - A flat bonus helps cheaper top receivers just as much, and the builder keeps picking those.
5. **Winning lineups do lean on the opponent's top receiver, and our builds do not.**
   - Stacked-QB lineups in the 2026 Millionaires, Weeks 1–4:

     | | Bring a player back from the other team | That player is the opponent's top-salaried receiver |
     |---|---|---|
     | The whole field | 47% | 18% |
     | The top 1% | 62% | 30% |
     | The top 0.1% | 66% | 33% |

   - It held in Weeks 1, 2 and 4 (W4: 53% vs 20%), but not in Week 3.
   - Our rebuilt Week 2–4 books did it in only 1–4 of 26 lineups a week, below even the field.

## The tests

**Done tonight: the Weeks 2–4 replay on the real contests.** These weeks are in-sample, and Week 4 chose the idea, so
this is descriptive only. Each cell is the chance of at least one big seat on your Week-5 plan.

| The 8 block lineups get | Week 2 | Week 3 | Week 4 | Lamb, Week 4 |
|---|---|---|---|---|
| nothing | 0.010 | 0.002 | 0.30 | 0 |
| cheap +2 (your Week-5 trial) | 0.11 | 0.018 | 0.66 | 0 |
| the top receiver +2 | 0.45 | 0.018 | 0.46 | 0 |
| cheap or top receiver +2 | 0.45 | 0.019 | 0.42 | 0 |

Week 2 improved: Lamb boomed that week, and the block put him in 6–7 lineups. Week 4 got worse. The block raises
top-receiver exposure in general, but it does not build the Stroud–Collins–Lamb lineup.

**Running tonight: study 70, the decisive test on past seasons.**
- The other reviewer builds it; production checks it.
- It uses the same historical-slate harness as studies 63 and 65: 2023–24 decides, and 2022 must not contradict it.
- The arms are "top receiver +2" and "cheap or top receiver +2", each against your live cheap block.
- Only if one is enterable can you choose it at Saturday's arming. The block file is built and tested
  (`scripts/top_wr_block_file.py --with-cheap`), and Friday's practice run would rehearse it.
- Honest prior: blocks 51, 63 and 65 all failed against the cheap block, so expect "not enterable" more likely than not.

**Proposed for Week 6: study 71, the structural fix.**
- In the lineup shapes that require a player from the other team (58% of rows), that player would be the opponent's
  top-salaried receiver.
- This needs a new option in the lineup builder, in both code bases, so it can't be done safely this week. It would be
  tested the same way first.

## How much this bears

- Week 4 chose the idea, so Week 4's numbers prove nothing on their own.
- The bring-back pattern is four weeks of real contests, and it reversed in one of them.
- The decision belongs to the harness test, and then to you.

Evidence: `reports/2026-10-08-topwr/` (the replay script, scores, log, and the mechanics probe).
