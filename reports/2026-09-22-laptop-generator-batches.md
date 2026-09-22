# Construction: `lev` spends 20% of the generation budget and never reaches the ceiling; every top-1% lineup came from `boom`

Assignment from `f63cecda` (the half complementary to production's field study). Script:
`reports/lab-handoffs/2026-09-22-generator-batches-week2.py`; the criterion is in its header, written
before running.

**Pool:** the Week-2 run built 2026-09-19 15:30Z (draft group 153428), 12,555 unique candidates.
Receipt config: `lev` 2,560 solves (`optimize_many` on `proj_tourney`) and `boom` 10,240 solves (one
optimal lineup per simulated world, worlds visited in "total" order; 9,995 unique). There are **no
other batch tags** (no `dark` or role families) in this generator. Realized score = sum of each
player's DK points from the real Millionaire file. Top 1% = realized ≥ **156.69** (126 lineups);
pool best 197.26; the Millionaire field has 260 entries at or above the pool's best.

## By mechanism

| batch | pool share | mean | p99 | best | top-1% hits | expected | lift | p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **boom** | 79.6% | 98.0 | 158.6 | **197.3** | **126** | 100.3 | 1.26 | <0.001 |
| **lev** | 20.4% | 75.7 | 127.8 | 149.5 | **0** | 25.7 | **0.00** | <0.001 |
| lev, each solve-order quintile | 4.1% each | 73–77 | 124–132 | 133–150 | 0 each | 5.1 each | 0 | 0.010 |
| boom world-order Q1 (first 20%) | 15.9% | 99.2 | 159.3 | 181.8 | 31 | 20.1 | 1.55 | 0.015 |
| boom world-order Q2–Q5 | 15.9% each | 97–98 | 158–159 | 184–197 | 23–26 | 20.1 | 1.15–1.30 | 0.19–0.54 |

## Is `lev` just contaminated? Partly — but not only

`lev` is far more exposed to non-players than `boom`: **47%** of `lev` lineups start a QB who took no
snaps (Bagent 1,185, Keenum 677, Mills 279, Lance 162: backups, because the run predates the QB
gate), and **82%** hold at least one zero-snap player (`boom`: 12.6% and 40.5%).

On the **clean** pool (no zero-snap player, 6,410 lineups, 110 of the 126 top-1% lineups kept):

| | n | mean | p99 | best | top-1% hits | expected | lift |
|---|---:|---:|---:|---:|---:|---:|---:|
| boom | 5,944 | 103.5 | 161.7 | 197.3 | 110 | 102.0 | 1.08 |
| lev | 466 | 89.6 | 134.1 | 149.5 | **0** | 8.0 | **0.00** (hypergeometric P = 0.0002) |

**Clean `lev` still never reaches the ceiling.** That is expected from its design: it maximises one
deterministic objective under diversity constraints, so its lineups cluster around the mean, while
the top 1% are world-specific outcomes, which is what `boom` samples. The lab recorded the same
pattern as an open question (`nfl2 scripts/build_knowledge_graph.py`, `q:lev-ceiling-error`: across
twelve 071/078 panels, lev was 3.2% of selections with **zero** 210+/220+ hits vs boom's 117/30).
Week 2 now adds a pool-level observation: zero in the top 1% of 12,555. Despite that, the Week-2
book took **8 of its 97 lineups from `lev`**.

## Structure (clean `boom` only, so neither the tag nor contamination can confound it)

| | n | top-1% hits | expected | lift | p |
|---|---:|---:|---:|---:|---:|
| $0 salary left | 1,152 | 28 | 21.3 | 1.31 | 0.14 |
| $100–300 left | 1,828 | 43 | 33.8 | 1.27 | 0.07 |
| **$400–1,000 left** | 2,964 | 39 | 54.9 | **0.71** | **0.003** |
| QB+2 / QB+3+ | 4,181 / 1,763 | 82 / 28 | 77.4 / 32.6 | 1.06 / 0.86 | — |
| RB in QB stack / not | 1,686 / 4,258 | 27 / 83 | 31.2 / 78.8 | 0.87 / 1.05 | — |

The stack-size and RB-in-stack differences seen on the raw pool disappear once contamination is
removed. **Unused salary survives:** lineups leaving ≥ $400 are half the clean pool and under-produce
top-1% lineups by 29%.

**Not measurable from the pool:** every candidate has a bring-back and at least QB+2, because both are
generator constraints (100%). Whether those constraints cost ceiling can only be seen in the field.
**Production's half:** please report what share of the Millionaire's 232+ / 250+ lineups have no
bring-back, a naked QB or a QB+1, and how much salary they leave.

## Nominations (not adoptions — Week 2 only, one slate)

1. **Move `lev`'s 2,560 solves to `boom`** (more worlds), or drop `lev` from the pool the selector
   sees. Replicate on Week 1 first (production holds that pool; the script takes a run dir), then run
   a lab panel with a co-run control under the six-season law.
2. **A salary floor** (e.g. spend ≥ $49,700) on `boom` solves, as a lab arm; one slate only.
3. The `boom` world order front-loads slightly better worlds (Q1 lift 1.55, p = 0.015; Q2–Q5 null).
   That is weak and not actionable alone.

Limits: one slate; players absent from the ownership file (nobody drafted them, mostly backups)
score 0; the pool is the Saturday 15:30Z build, not the Sunday T-70 rebuild.
