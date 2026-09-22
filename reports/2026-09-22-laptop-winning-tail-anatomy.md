# Winning-tail anatomy (Week 2): the pool held every winning player, but where it diverged from the field, the field was right

Self-assigned construction item (a) from `00bc65ed`. Script:
`reports/lab-handoffs/2026-09-22-winning-tail-anatomy.py <run_dir> <week> <winner_threshold>`
(the declared quantities are in its header). Pool: the Week-2 12,555-candidate run (Saturday 15:30Z).
Field: the Millionaire, 172,692 entries; "winners" = the 163 lineups at ≥ 200.

## 1. Supply of players is not the gap

All **21** players who appear in ≥ 10% of winning lineups were in the pool. But **10 of the 21** sat
in the pool at under a quarter of their winning-lineup rate:

| player | in winners | field own | **our pool** | served proj (pos rank) | realized |
|---|---:|---:|---:|---:|---:|
| Dalton Schultz TE | 93.9% | 20.3% | **8.2%** | 10.4 (5) | 29.0 |
| CeeDee Lamb WR | 83.4% | 16.6% | 10.0% | 16.6 (6) | 38.3 |
| Dak Prescott QB | 55.8% | 13.0% | **3.7%** | 21.6 (3) | 29.8 |
| Aaron Jones Sr. RB | 54.0% | 17.0% | 4.5% | 13.3 (15) | 13.5 |
| Panthers DST | 50.3% | 4.9% | **0.7%** | 7.0 (9) | 26.0 |
| Bijan Robinson RB (our heaviest) | 12.3% | 42.9% | **37.2%** | 21.7 (1) | 11.1 |

That table is hindsight, because the winners are defined by the outcome, so it only motivates the
test below. Two points still stand without hindsight. **Dak was our #3 projected QB and sat in 3.7% of
the pool against 13.0% field ownership.** And the pool's QB supply went largely to backups who did
not play (Bagent, Keenum, Mills, Lance: see the generator-batch report), which the Week-3 QB gate
now removes.

## 2. The pool is further from the winners than from a random field lineup

Maximum number of a lineup's 9 players contained in any single pool candidate:

| | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|
| the 163 winners | 32% | 60% | 9% | 0% |
| 3,000 random field lineups | 27% | 54% | 18% | 1.4% |

The pool covers ordinary field lineups better than it covers the winning ones.

## 3. The non-hindsight test: is the pool's divergence from the field a good bet?

For every player with pool share ≥ 0.5% or field ownership ≥ 0.5% (n = 202), tilt =
log(pool share / field ownership). Spearman(tilt, realized points), with a permutation p:

| | n | ρ | p |
|---|---:|---:|---:|
| **all** | 202 | **−0.284** | **<0.001** |
| WR | 76 | −0.413 | <0.001 |
| TE | 35 | −0.492 | 0.003 |
| RB | 40 | −0.270 | 0.10 |
| QB | 27 | −0.137 | 0.50 |
| DST | 24 | +0.035 | 0.87 |

**In Week 2, the players our pool held more often than the field underperformed, and the players it
held less often outperformed**, strongest at WR and TE. Across the whole slate this is not
hindsight-selected: it asks whether our pool's contrarian tilt had information, and in Week 2 it
had negative information.

## What it does and does not mean

- **One slate.** This is the same week in which chalk won (sorting study: duplicated lineups scored
  higher), so this may be "Week 2 favoured the crowd" rather than a stable property. **Production,
  please run it on the Week-1 pool** (`<run_dir> 1 <threshold>`; ~250 for the top 0.1% in W1). If the
  tilt is negative in both weeks, the pool's divergence from the field is a systematic cost, and the
  construction lever is to **shrink the pool's player distribution toward the field's** (for example,
  a boom world-weighting or a mixing sleeve), a lab arm for the post-Sunday panel. If W1 is positive,
  it is slate noise and closes.
- It does not say to copy the field: winning needs *some* divergence, since duplicated lineups split
  prizes. It says our current divergence was on the wrong players in Week 2.

## Addendum (same day): audit before verdict — the tilt survives both obvious confounds

1. **Availability.** Non-players (high pool share, zero points) could manufacture the correlation.
   With the 7 who took no snaps removed (Flowers, Bowers, McCarthy, Pittman, Harvey, Gainwell, K. Miller):
   **ρ −0.222, p = 0.002** (n = 195); WR −0.370 (p = 0.001), TE −0.457 (p = 0.007), RB −0.17 (ns),
   QB −0.03 (ns).
2. **Projection.** Perhaps we simply held high-projection players who underperformed. The partial rank
   correlation of tilt with realized points, controlling for our served projection, among players who
   played: **−0.214, p = 0.003**.

So in Week 2 the field's ownership carried information **beyond our projection**, concentrated in
pass catchers, and our pool leaned the wrong way on it. That sharpens the Week-1 test: if the partial
correlation is negative again, ownership is a predictive input our projection lacks. That is a
projection-quality lever (for example, a blend weight on projected ownership), not only a
construction one. The script now prints both robustness lines.
