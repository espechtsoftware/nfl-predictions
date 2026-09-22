# The Week-2 inversion is real at −0.49, and availability is driving it

Extends production's regime-flip report (`a6984c29`). I set out to check whether the
inversion was n=2 noise. It is not — it is far larger than reported, it reproduces on an
independent bank, and its mechanism is measurable.

## 1. The inversion, at candidate level

Production binned P(≥ cash line) into deciles and got Spearman −0.094 for Week 2. At raw
candidate level over all **12,555** candidates:

| simulated quantity | Spearman vs realized | p |
|---|---:|---:|
| `sel_mean` (selection bank) | **−0.4908** | ~0 |
| `sel_p194` | −0.4296 | ~0 |
| **`aud_mean` (independent audit bank)** | **−0.4908** | ~0 |
| `aud_p194` | −0.4325 | ~0 |

**Top decile by simulated mean realized 69.83. Bottom decile realized 109.33.** The lineups
the simulator liked most scored **40 points worse** than the ones it liked least.

The audit bank is an independently seeded simulation and returns the identical −0.4908, so
this is not a bank artifact. **The flip is real and it is much stronger than the binned
statistic suggested.**

## 2. The mechanism: players who were never going to play

**37 players were projected ≥ 5.0 and scored exactly 0.0.** The largest:

```
WR  Zay Flowers      22.57     <- Doubtful
QB  Tua Tagovailoa   17.47
QB  J.J. McCarthy    15.91
QB  Case Keenum      15.55     <- backup
QB  Tanner McKee     14.31     <- backup
QB  Sam Ehlinger     14.26     <- backup
```

**Five of the top six are quarterbacks** — production's dead QB slot, by name. **53.1% of
the entire pool carries at least one of these players.**

And the relationship is monotone in both directions at once:

| dead players in lineup | n | mean realized | **mean simulated** |
|---|---:|---:|---:|
| 0 | 5,893 | **103.46** | 121.88 |
| 1 | 4,748 | 88.94 | **126.42** |
| 2 | 1,777 | 75.86 | **131.53** |
| 3 | 132 | 68.22 | 129.22 |

**As realized score falls, the simulator's rating rises.** That is the inversion, in one
table. It is not mysterious: a player who will not play is served `E[points | played]` at
14–22 points, so a lineup that stuffs three of them looks outstanding and scores nothing.
The optimizer is doing its job perfectly against a corrupted objective.

## 3. Availability is a major driver, but not the whole story

Restricting to the 5,893 candidates carrying **zero** dead players:

| population | n | Spearman |
|---|---:|---:|
| all candidates | 12,555 | **−0.4908** |
| zero dead players | 5,893 | **−0.3720** |

Removing the mechanism entirely recovers about a quarter of the inversion and **leaves −0.37
behind**. So availability is a large, fixable component — and something else is also wrong.
I am not speculating about what; it is the next thing to measure.

## 4. What this chains together

Four findings from today are one causal chain:

1. **Projections serve `E[points | played]` with no availability weighting** (mine, this
   afternoon: QB 40.6% played vs 72–77% at skill positions).
2. **So unavailable bodies carry 14–22 point projections** — 13/13 Doubtful zeros, backup
   QBs at 10.1% snap rate, 70% of all QB rows.
3. **Lineups stuffed with them rate highest and score lowest** — the table above.
4. **Which inverts the simulator's ordering** (−0.49) and **loses the week at the floor**
   (book mean 98.40 vs field median 113.82).

That makes the availability repair look different from how production and I have both been
pricing it. Production bounded the reclaimed QB fifth at **~1.7 points** under the ceiling
law, and I agreed. **That prices it as a supply improvement.** But the table in §2 says the
same defect is corrupting the *objective* — and an objective that ranks backwards costs far
more than 1.7 points, because every downstream lever inherits it.

**That would also explain why nothing replicates.** Every instrument production listed as
flipping sign between the weeks is downstream of this ordering. If Week 1's pool was less
contaminated, its ordering held (+0.255) and levers behaved; Week 2's inverted and they
reversed. **Regime-dependence may not be irreducible — it may be an availability-contamination
level that is measurable pre-lock**, since who is a backup QB and who is Doubtful is known
before kickoff.

## 5. What I am not claiming

- Not that the 37 are all *unavailable* — "projected ≥5, scored 0.0" also catches a player
  who dressed and did nothing. The QB names make availability the obvious reading, but the
  clean test is snaps per player-week, which I have and will run next.
- Not that removing them fixes ordering — it demonstrably does not, −0.37 remains.
- Not that Week 1 shows the same structure. **I do not hold the Week-1 pool.** §4's
  explanation of the regime flip is a hypothesis with one slate behind it, and the Week-1
  candidate file settles it. That is the same artifact I asked for at `7c9de246`, and it
  is now the most valuable thing I could be given.
