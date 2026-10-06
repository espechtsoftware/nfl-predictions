# How the winners spread their players, and why our caps cost (your question, 10-06)

2026-10-06, written for you. Descriptive only: it measures how lineups are built, never how they scored, and it changes
nothing on Sunday by itself. Names stay out of this public file: "the winner you follow" is the user you asked us to study
on 10-05 (label User15 in our files); the agents give you his name in chat.

**Your question:** "Is it because we aren't choosing suitable alternatives or because we suddenly are losing a stack
because the QB has changed? ... Is their pool better only because of their volume? ... I want to find a way to reduce my
dependency on so many players while having suitable alternatives to pivot to. Would neo4j help?"

## The short answers

1. **Their spread is how they build, not only how many lineups they enter.** Cut a regular's 150 lineups down to a
   random 26, our size, and you still find only about 2 players in more than 40% of them. Our 26-lineup book has about
   10. Players who really enter 20–40 lineups look the same as the regulars: about 3 players over 40%.
2. **When a cap removes a player, the replacement comes from another game. That is true of the winners as well.** It
   is just how the slate is made up: most comparable players are in other games. The winners don't swap within the same
   game either. What differs is the shape: they keep 1–3 players heavy and spread the rest across many more quarterback
   stacks.
3. **The quarterback cap does split our top receivers from their quarterbacks.** But the winners' most-used receiver
   is also usually played without his own quarterback, so that is not where we differ.
4. **"They stack with the top receiver": partly true.** The team's top receiver is in about 60% of a regular's lineups
   with that quarterback, the same as our winners'-mix book. Their usual second choices are the second receiver or the
   tight end.
5. **Neo4j helps you look, not measure.** It is loaded Wednesday afternoon (see the end).

## 1. Volume or construction?

Most-used players other than the quarterback, as a share of a portfolio's lineups. Medians over 2026 Weeks 1–4 of the
Millionaire. Users were picked by how many lineups they entered, never by how they finished.

| | Top 1 | Top 3 | Top 10 | Players over 40% | Over 30% | Different players | Quarterbacks |
|---|---|---|---|---|---|---|---|
| The 117 regulars (150 lineups) | 49% | 35% | 20% | 1 | 4 | 78 | 18 |
| The regulars cut to 26 lineups | 53% | 38% | 21% | 2 | 5 | 53 | 11 |
| Real players with 20–40 lineups | 60% | 43% | 23% | 3 | 6 | 46 | 10 |
| The winner you follow, cut to 26 | 44% | 32% | 20% | 1 | 3 | 63 | 13 |
| **Our winners'-mix book (26)** | 50% | 50% | 41% | **9–10** | 12 | **25** | 7 |
| Our real books, Weeks 1–3 | 40% | 26% | 15% | 1 | 2 | 99 | 23 |
| Our real book, Week 4 | 51% | 47% | 40% | 9 | 13 | 34 | 6 |

The winners' most-used player is about as heavy as ours, or heavier. The difference is what comes after: their usage
falls off quickly, while ours stays flat at the cap (13 of 26 lineups) for about ten players. They also use roughly
twice as many different players and about half again as many quarterbacks.

## 2. When the most-used player is left out, who takes his place?

In the lineups without a portfolio's most-used non-quarterback player, these are the players at his position:

| | Same team | Same game | Another game | Projected points vs him |
|---|---|---|---|---|
| The regulars | 0% | 4% | 96% | −3.2 |
| Real players with 20–40 lineups | 1% | 4% | 95% | −2.4 |
| The winner you follow | 0% | 4% | 96% | −3.0 |
| Our winners'-mix book | 3% | 4% | 93% | −0.7 |

Nobody swaps within the game: the comparable players are mostly in other games. The winners also accept a cheaper,
lower-projected player there (about 3 points less), presumably spending the salary elsewhere. Our book replaces him with
nearly as good a player (−0.7), which is why our lineups end up holding the same ten players.

The tighter player cap (study 36) works the same way: 93% of the replacements came from other games, the slate's own
proportions, at about 0.8 points each. Every lineup kept its quarterback stack.

## 3. The quarterback cap and the top receivers

Under the quarterback cap (study 35), our top receivers kept about half the book, but fewer of their lineups had their
own quarterback with them: 27% before the cap, 21% after. The winners' most-used receiver is with his own quarterback
only 15–19% of the time, and in about 45% of his lineups he has no teammate or opponent with him. So this is a real
effect of the cap, but it is not a difference from the winners.

## 4. Do they stack the quarterback with his top receiver?

| | Quarterback's lineups with his team's top receiver (by salary) | Receivers paired: WR1 / WR2 / TE1 |
|---|---|---|
| The regulars | 60% | 42% / 23% / 26% |
| Real players with 20–40 lineups | 61% | 49% / 19% / 21% |
| The winner you follow | 55% | 46% / 21% / 24% |
| Our winners'-mix book | 58% | 39% / 21% / 32% |
| Our real books, Weeks 1–4 | 69–87% | 33–44% / 8–25% / 21–48% |

The top receiver is their most common partner, but not a rule. Measured by our projection rather than salary, the
regulars reach 69% and our winners'-mix book 54%, so our mix leans a little more on the tight end than they do.

## What this means for the next test (study 37, the reviewer's)

Swapping within the same game is out: the winners don't do it. What they do differently is the shape:
- 1–3 heavy players;
- many more quarterback stacks (10–11 quarterbacks per 26 lineups against our 7), each with its top receivers;
- and a cheaper filler where the heavy player is left out.

The reviewer is designing a test of that shape against the book you chose, on fresh practice weeks. As always, nothing
changes for Sunday without the test and your yes.

## Neo4j

Yes, for looking; the numbers above come from scripts that can be re-run and checked. On Wednesday afternoon, outside
build times, the 117 regulars' complete Week 1–4 portfolios are loaded into the local graph, together with the top
1,000 lineups of each week. You can then open http://localhost:7474 and ask, for any user and week, which players
form his core, which receivers go with each of his quarterbacks, and who took a given player's place. The graph never
runs during a Saturday or Sunday build.
