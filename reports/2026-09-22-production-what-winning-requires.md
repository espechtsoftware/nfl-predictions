# What winning actually requires — and the strategy/target mismatch it exposes

Operator: *"winning is the goal, so we need to figure out quickly how it would be
possible."* This computes it from the realized distributions — our actual candidate
pool against the actual 831,028-entry field — rather than arguing it.

It also corrects an overstatement of mine: I said "$400 isn't reachable," conflating
*first place in a large GPP* with *winning $400*. Those are different bars and only the
first is closed.

---

## 1. The money record, so the target is concrete

From the DK entry history (local only — never committed):

| | entries | fees | won | net | cashed |
|---|---:|---:|---:|---:|---:|
| Week 1 2026 | 80 | $399 | $140 | −$259 | 18 (22.5%) |
| Week 2 2026 | 97 | $246 | $26 | −$220 | 3 (3.1%) |

Across **1,164 lifetime entries**: best week ever **$140**; best single entry ever
**$100** (rank 505 of 132,352); entries ever returning ≥$400: **zero**.

**Two priors corrected by this record.** ROI is *best* in the largest fields
(>200k: −48.7%) and worst in the smallest (<100: −100%) — I had suggested small-field
contests, and the record says the opposite. And it is driven by payout *shape*: >25%
places-paid returns −34.7%, top-heavy (<2% paid) returns −100% over 85 entries.

## 2. Winning a large-field GPP is closed

P(win) with 150 entries against the real Week-1 Millionaire field, as a function of a
**uniform edge added to every lineup we build**:

| edge | our pool mean | field percentile | P(win), N=150 | P(win), N=500 |
|---:|---:|---:|---:|---:|
| **+0 (actual)** | 141.1 | **49th** | **0.0%** | **0.0%** |
| +20 | 161.1 | 75th | 0.0% | 0.0% |
| +30 | 171.1 | 84th | 0.2% | 0.5% |
| +40 | 181.1 | 91st | 7.7% | 21.9% |
| +60 | 201.1 | 98th | 53.5% | 85.9% |

**+40 points on every lineup** — 28% better than the field average — buys a 7.7% shot.
That is not a target anyone reaches. The 831k Millionaire is closed, and this is the
proof rather than the assertion I offered earlier.

The reason is structural, not a failing of ours: the winner is the **maximum of 831,028
draws** and we take about 150. Our pool's max grows ~6.95 points per e-fold of
candidates; the field's winning line grows ~6.41 per e-fold of entries. **The two grow
at the same rate**, so no amount of volume closes a fixed deficit — we are running the
same race from five e-folds back.

## 3. But winning is not closed — the winnable frontier

Same computation across field sizes, N=150:

| field size | **+0 (today)** | +10 | +20 | +30 |
|---:|---:|---:|---:|---:|
| 200 | **72.8%** | 87.6% | 96.2% | 98.9% |
| 500 | **24.7%** | 52.6% | 77.7% | 92.0% |
| 1,000 | **10.7%** | 32.4% | 60.5% | 84.6% |
| 2,500 | 3.9% | 15.0% | 38.1% | 68.2% |
| 5,000 | 0.7% | 8.5% | 24.6% | 54.4% |
| 25,000 | 0.0% | 0.4% | 9.2% | 23.7% |
| 100,000 | 0.0% | 0.0% | 1.6% | 11.7% |
| *field percentile* | *49th* | *62nd* | *75th* | *84th* |

**We can already win contests up to about a thousand entries** at 10–25% a week. And
the returns to modest edge are steep and convex: **+10 points per lineup — 49th to 62nd
field percentile — roughly triples the win rate at every size** and opens 5,000-entry
fields.

**The honest caveat on those numbers.** P(win) here is bought largely with *share of
field*: 150 entries in a 1,000-entry contest is 15% of it. At parity quality, buying
share is just paying rake — you win sometimes and lose on average. **The win
probabilities above are real; the profit is not, until there is edge.** Edge is the only
thing that converts them into money.

## 4. The mismatch this exposes

Our Week-1 pool sat at the **49th field percentile** and Week 2 at the **22nd**. The
average lineup we generate is a median DFS entry.

Meanwhile the programme's whole evidence ledger is denominated in **tail counts** —
weeks with a lineup ≥194, ≥220, the 27/107 baseline, tail-supply agendas. Those are the
currency of winning a large-field Millionaire, and section 2 shows that contest is
closed to us at any achievable quality.

**We are running a tournament-winning construction in contests we cannot win, and
paying the cost of differentiation without being able to collect its prize.** The
diversification that lowers our mean is correct only if the ceiling it buys can reach a
winning line. It cannot.

The measurements point the same way from every side: no coverage misses, a concentration
gap that is constant across both weeks, per-player projection accuracy that is stable,
and a ceiling that grows logarithmically. None of those is the binding constraint. The
binding constraint is **where our lineup distribution sits against the field's**.

## 5. The proposed target change

Replace "produce a ≥194 lineup" with a measurable, field-relative objective:

> **Move the pool's mean from the 49th to the 65th+ percentile of the actual contest
> field, measured weekly against captured standings.**

It is directly measurable every week from `contest_entries` (we now have 994,328 Week-1
and 311,664 Week-2 rows). It is the quantity the winnable-frontier table is a function
of. And it is a target the programme has **never optimised for** — which is the most
encouraging fact in this report, because it means the obvious work has not been done
rather than done and exhausted.

Known contributors already measured, in order of size:
1. **Field-relative concentration** — the field's top play reaches 88% exposure, our
   most-used 61%; mean signed gap +10pp on their top 40. Largest single lever, and the
   one requiring genuine ranking skill.
2. **The dead QB slot** — ~20% of every pool, worth ~1.8 points of pool mean. Merged
   today, awaiting the image.
3. **Doubtful exclusion** — +7.26 Week-2 book mean, already live.
4. **The simulator regime flip** — the ranking inverts between weeks; it is why no
   simulator-dependent lever replicates.

## Scope

Two slates. The closed-ness of the large-field GPP is robust: it follows from the
same-slope growth law measured at R² 0.98/0.96 and does not depend on our two weeks
being typical. The winnable-frontier table uses Week-1 quality, which was our *better*
week — Week 2 numbers are worse everywhere.
