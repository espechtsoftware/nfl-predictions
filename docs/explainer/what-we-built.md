# A machine for finding out we're wrong

*A one-page, non-technical explanation of the system. Plain-text companion to
`what-we-built.html`.*

It plays daily fantasy football. But the interesting part was never the
predictions — it's that the whole thing is built, above all, to catch itself
being wrong. Recently it did, and the answer was surprising.

---

## The game

Pick nine NFL players under a salary cap. Enter eighty different lineups against
a field of roughly 160,000 opponents. Only scores at the very top win real money
— finishing five hundredth out of 160,000 pays close to nothing.

## The counterintuitive part

That makes *accuracy* nearly worthless. If all eighty lineups are pretty good,
you win nothing at all. You need one of them to be extraordinary.

So the system optimises for its single best entry and deliberately ignores the
average. Which is why we can say, without contradicting ourselves, that our
player forecasts got better while our results got worse.

## The discovery

Imagine a weather service that predicts each city's chance of rain beautifully,
but has no concept of storms — it treats every city as independent. City by city,
it looks perfectly calibrated. Ask it whether it will rain in five cities at once
and it's hopeless.

That was our system. The individual player forecasts were fine. But when a
quarterback has a monster game, his own receivers are more than **three times**
as likely to have monster games too — and our simulator believed that number was
about **one**. It thought teammates were essentially unrelated.

| | |
|---:|:---|
| **1.05** | what our simulator believed |
| **3.32** | what actually happens |

*How much more likely a receiver is to have a huge game once his own quarterback
has one, compared with chance alone. A value of 1.00 would mean teammates are
completely unrelated.*

Winning requires several players on one team erupting together. We were
systematically failing to imagine the exact scenarios that win.

We didn't guess this. We measured it — and that one number went on to explain a
year of otherwise baffling failures.

## Why the method is the real product

Before every experiment, we write down in advance what would count as success.
Then the code is frozen into a sealed image so it can't be quietly adjusted
afterwards. The experiment runs once. If the result is disappointing, it gets
recorded as disappointing.

There are now around 120 numbered entries in the project's lab record, including
retractions of our own earlier conclusions. More than twenty experiments are
closed as failures, each with the reason it failed.

We have also repeatedly found bugs that were making our own past results look
better than they were — injury news that arrived after lineups locked, betting
lines from after the deadline, a player's end-of-season position leaking
backwards into September. Every time, we threw out the flattering numbers and ran
it again.

That sounds like bureaucracy. It's the opposite. It's the only reason anything
we've found can be believed.

## Where it stands

| | |
|---|---:|
| Weeks the top prize was beaten | 0 of 68 |
| Typical gap to the winning score | ~57 pts |
| Weeks the portfolio wins its money back | ~7 in 10 |
| Weeks it wins the tournament | ~0 |

The system is not yet profitable at the top prize, and it says so in writing.
What it has produced instead is a specific, measured explanation of *why* — which
is a far better position than a good-looking result nobody can trust.

---

Most projects build a machine that tries to be right. This one is a machine for
finding out exactly how it's wrong — and it just told us something specific and
surprising.
