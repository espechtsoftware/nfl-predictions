# The dead QB slot, the Doubtful zeros and the floor failure are one defect

Confirming and extending production's `bbc24a08` with an independent instrument, and then
showing that the obvious fix does not work.

## 1. Their QB finding replicates on a different measurement

Production measured backup QBs at roughly 15% playing. I measured **snaps** — the instrument
I built for the Doubtful work — over 2026 Weeks 1–2 classic slates:

| QB band | slate rows | **took a snap** | mean salary |
|---|---:|---:|---:|
| backup (≤ $4,600) | 159 | **10.1%** | $4,048 |
| starter (> $4,600) | 68 | **83.8%** | $5,681 |

Confirmed, and slightly starker than their figure. Note also that backups are **159 of 227
QB slate rows — 70% of every QB on the board.**

## 2. It is not a QB problem. It is an availability problem, and QB is where it bites

Same measurement across positions, against the served projections:

| pos | n | **% played** | mean proj | mean realized |
|---|---:|---:|---:|---:|
| **QB** | 160 | **40.6%** | 8.53 | 6.07 |
| RB | 206 | 72.3% | 6.50 | 5.63 |
| WR | 333 | 74.2% | 6.10 | 5.31 |
| TE | 215 | 77.2% | 3.50 | 3.47 |

**Three in five slate QBs never take a snap**, against roughly one in four elsewhere. The
projection layer serves `E[points | played]` unconditionally, so a body that will not play is
priced as if it will.

**That is the same defect I measured this morning from a different angle**: 13 Doubtful
player-weeks, zero snaps, 0.0 points each, at the highest mean salary of any status cohort —
and production's own note that five Doubtful players scored exactly zero against a mean
projection of 12.32. Doubtful players, backup quarterbacks and the Week-2 floor failure are
three symptoms of one cause: **nothing multiplies a projection by the probability that the
player appears.**

The Doubtful denylist is a point fix for one symptom. It does nothing for the 70% of QB rows
that are backups with no status flag at all — they are not Doubtful, not Out, not
Questionable. They are simply not going to play.

## 3. The obvious fix over-corrects, and I checked before proposing it

If projections are `E[points | played]`, the natural repair is to multiply by `P(play)`.
Using each position's own play rate:

| pos | proj × P(play) | actual mean realized | verdict |
|---|---:|---:|---|
| QB | 8.53 × 0.406 = **3.46** | 6.07 | over-corrects by 43% |
| RB | 6.50 × 0.723 = **4.70** | 5.63 | over-corrects |
| WR | 6.10 × 0.742 = **4.53** | 5.31 | over-corrects |
| TE | 3.50 × 0.772 = **2.70** | 3.47 | over-corrects |

**A uniform per-position multiplier is wrong in the same direction every time**, because the
players who do not play are disproportionately the *low-projection* ones. Scaling the whole
position drags down the starters, who were fine.

So the correction has to be **per-player `P(play)`**, not a cohort constant. That is a
modelling change with a training contract, not a coefficient — and it is exactly the kind of
thing that needs a preregistration rather than a patch.

## 4. One caution about a column I nearly reported

My first cut also computed *realized-if-played ÷ projection*, which reads **1.697 for QB** —
and looks like the projections are badly under-calibrated. **It is not a calibration number
and I am not reporting it as one.** The numerator averages only QBs who played (nearly all
starters) while the denominator averages all QBs including backups; the two populations are
different, so the ratio measures the population gap, not accuracy. Flagging it because the
number is striking, it will reappear for anyone who runs this query, and it means nothing.

## 5. Where this lands against production's ceiling law

Production priced the reclaimed QB fifth at about **1.7 points** under the measured
logarithmic ceiling law — against the ~35 needed to reach a winning line. **I agree that
bounds the prize and I am not arguing it is a ceiling fix.**

The value is elsewhere: it is a **floor** fix, and Week 2 was lost at the floor (book mean
98.40 against a field median of 113.82). It is also the cheapest lever on the board in the
sense that matters here — it removes rows that *cannot* pay rather than trying to find rows
that might, and its evidence base (13/13 Doubtful, 10.1% backup QBs, three-in-five slate QBs)
is stronger than anything in the ledger's tail work.
