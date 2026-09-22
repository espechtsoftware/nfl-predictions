# One in five of every pool is dead at the quarterback slot

Second production report of 2026-09-22, following
`reports/2026-09-22-production-ceiling-and-eligibility.md`. This one decomposes *why*
our candidate pool sits where it does against the real field, using the 994,328 +
311,664 captured field lineups. It ends at a single both-weeks defect with a known
mechanism, and it retracts two intermediate readings of my own on the way.

---

## The comparison that matters: our pool against the actual field

| | our pool mean | field mean | gap | pool mean at field percentile |
|---|---:|---:|---:|---:|
| Week 1 | 141.06 | 142.07 | **−1.02** | 49.1 |
| Week 2 | 93.67 | 115.55 | **−21.88** | 21.6 |

Week 1 our candidate pool was dead level with the Millionaire field. Week 2 it was in
the bottom quartile. Selection *adds* value in both weeks — the book mean sits above
the pool mean in field-percentile terms both times (49.1 → 60.2, 21.6 → 27.9), so the
selector is not the defect.

Rows landing in the field's top 20%: **Week 1 27.8%** of our book (1.39× an average
entry), **Week 2 6.2%** (0.31×).

## Two readings I formed and then had to drop

**Not coverage.** Of the 40 most-rostered players in the top 1,000 field lineups,
**zero** were missing from our frame, in either week. Every player the winners used was
available to us.

**Not concentration.** The field is more concentrated than our pool, but by nearly the
*same* amount in both weeks — mean signed exposure gap **+9.9pp (W1)** and **+10.4pp
(W2)**, their top play at 81.7% / 88.1% against our most-used at 72.3% / 60.7%. Since
Week 1 was a −1.02 week and Week 2 a −21.88 week, a constant cannot be the cause. I had
read the Week-2 exposure table as "we spread thin while the field converged on chalk
that hit"; the Week-1 replication does not support it and I withdraw it.

**And not a projection-quality collapse.** At player level the two weeks are close:

| | bias | sd(err) | Pearson | Spearman |
|---|---:|---:|---:|---:|
| Week 1 | −0.56 | 6.46 | +0.695 | +0.671 |
| Week 2 | −1.12 | 5.84 | +0.611 | +0.638 |

I first computed *exposure-weighted* projection error (+22.54 W1, −31.37 W2 per lineup)
and read the 54-point swing as a projection failure. It is not: per-player accuracy is
nearly identical across the two weeks. The swing is dominated by the exposure weights —
which of our favourites happened to hit — and across two slates that is mostly variance.
Withdrawn as a defect claim.

## What does survive: the quarterback slot, both weeks, same sign

QB is the worst position in both weeks by a wide margin (bias −3.28 and −4.41; every
other position is within ±1.3). Splitting by salary finds all of it in one place:

### Cheap quarterbacks, ≤ $4,600

| | n | **actually played** | our projection | realized | bias | **share of our pool** |
|---|---:|---:|---:|---:|---:|---:|
| Week 1 | 29 | **13.8%** | 8.39 | 1.33 | −7.06 | **20.8%** |
| Week 2 | 33 | **15.2%** | 10.67 | 1.19 | −9.49 | **34.6%** |

Roughly thirty backup quarterbacks per slate, **about 85% of whom never take a snap**,
carry projections of eight to eleven points — and our generator puts one of them in a
fifth to a third of every lineup it builds. Counting only QBs who truly never played:
they occupy **19.5% (W1)** and **20.0% (W2)** of the pool. The same number twice.

Removing them removes the bias almost entirely:

| | all selectable QBs | QBs who actually played |
|---|---:|---:|
| Week 1 | −3.80 | **+0.80** |
| Week 2 | −6.81 | −3.24 |

**Mechanism, already on the books.** Backup quarterbacks carry E[points | played] as an
*unconditional* projection — the QB availability contract defect. A $4,000 depth-2 QB is
served at a mean near ten because that is what he would score *if he started*, and
nothing multiplies it by the probability that he does. This is the same defect class as
the Doubtful finding in the companion report, and a repair that conditions on
availability addresses both.

## Why volume cannot be the answer

Subsampling each pool at increasing sizes and taking the max realized gives a very clean
logarithmic law — **R² 0.985 in both weeks**:

| | fit | pool | ceiling | winning line | candidates needed to reach it |
|---|---|---:|---:|---:|---:|
| Week 1 | E[max] ≈ 181.75 + 6.95·ln(n) | 3,200 | 236.28 | 273.98 | **583,747 — 182×** |
| Week 2 | E[max] ≈ 126.49 + 7.60·ln(n) | 12,555 | 197.26 | 232.38 | **1,115,688 — 89×** |

About seven points per e-fold. Separately, fitting winning line against field size over
the twelve captured Week-2 contests gives **win ≈ 158.74 + 6.41·ln(field), R² 0.961** —
*the same slope*. Our pool's maximum grows with candidates at essentially the rate the
field's maximum grows with entries, so volume cannot close a fixed offset; it is a race
at equal speed from behind. At equal draw count the offset is explicit: a field of
12,555 entries wins at about 219, our 12,555 candidates top out at 197.26.

This is the strongest available argument that generation *quantity* is the wrong lever,
and it is why the 20% reclaimed below is framed as efficiency rather than as a path to
the winning line. It is worth about 1.7 points of ceiling, not thirty-five.

## What it costs, stated honestly

The selector mostly avoids these lineups — only **1 of 97** entered Week-2 rows used a
cheap never-played QB. So this is not a direct scoring loss on the delivered book. It is
a **generation-efficiency loss**: a fifth of every pool is built, solved and scored to
produce candidates selection will not use. Given that LEV generation is the expensive
serial stage (~10h at D12800), reclaiming that 20% is roughly a 20% throughput gain,
worth about 1.5 points of pool ceiling at the measured ~7 points per e-fold of
candidates. Modest, but free, and it makes the pool honest.

The Doubtful rule in the companion report is the piece with a measured effect on the
delivered book. This one is the larger and more systematic defect, and the cheaper
correctness fix.

## Also recorded

**DST projections carry essentially no rank skill** — Spearman **+0.167 (W1)** and
**+0.163 (W2)** against +0.50 to +0.80 for every skill position, in both weeks. Not
acted on here; recorded because it is consistent and because DST is a mandatory slot.

## Scope

Two slates. The QB finding is the strongest claim here: same sign, same mechanism, and
near-identical magnitude (19.5% / 20.0% of pool) across two slates that differ in almost
every other respect. The withdrawn readings above are why the rest is stated narrowly.
