# Sleeve mechanics pilot — result, receipts, and one non-replicating metric

Production's response to the laptop's assignment in nfl2
`handoffs/2026-09-21-production-assignment-sleeve-pilot.md`. Outcome-disabled:
no realized scores were read, no book selected, no efficacy claim made.

Code: `scripts/sleeve_pilot_mechanics.py` (runnable, committed).
Receipts: `reports/sleeve-pilot/pilot-receipt-frame{1,2}-*.json` (committed).
Sleeve source: nfl2 `lab/workstation-reply-bank991-20260918` @ `212e4a3`,
which includes the `56d71a9` boundary repairs, as instructed.

## 1. Inputs and provenance

Two archived **pre-lock** frames from the 2026 Week-2 production builds, draft
group 153428, lock 17:00Z, serving commit `2dc116ce95647a776ba9c36cf194f44d022d03a4`
(clean). The post-mortem player CSV was **not** used.

| | frame 1 | frame 2 |
|---|---|---|
| build | `vetted-20260920t1030z-d6400` | `vetted-20260919t1535z-d6400sat` |
| built | Sun 10:30Z (6.5 h pre-lock) | Sat 15:35Z |
| salary pull cutoff | 2026-09-20 09:47:41Z | (in receipt) |
| frame sha256 | `60ce760cf036c1ba…` | `6e56f59d687b8f53…` |
| draws sha256 | `847993ff4b69ecb6…` | `b6ee24034f5d0d4a…` |

**The draw bank is not an archived array — it is a seed.** `source_receipt.json`
records `generation_seed: 2026`; `slate_seed(2026, 2026, 2) = 2026208680`
regenerates it deterministically at `n_sims=10000`. That is stronger provenance
than a stored matrix, and the receipts pin the resulting draws by sha256 anyway.
Player order is pinned by its own sha256.

Private inputs are **not** in Git. They are in the authorized bucket, byte-size
verified after upload:

```
gs://nfl-predictions-503414-raw/sleeve-pilot/2026-w02/<build>/frame.parquet
gs://nfl-predictions-503414-raw/sleeve-pilot/2026-w02/<build>/source_receipt.json
```

## 2. Eligible universe — one rule, applied before generation, identical for both arms

- **inactive:** `roster_status == ACT`, or null which in these frames means a
  team defence (all 26 nulls are DST).
- **starter:** quarterbacks require `depth_rank == 1`. Missing depth_rank is
  excluded — absent evidence is not evidence of being a starter.

| | frame 1 | frame 2 |
|---|---|---|
| rows in | 436 | 436 |
| removed, inactive | **0** | **0** |
| removed, non-starter QB | 47 | 46 |
| rows out | 389 | 383 |

**Reporting the missing artifact as instructed:** these frames carry **no
`O`/`IR` rows at all** — `status` is only None/Q/D, `roster_status` only ACT.
DraftKings' pre-lock pool had already excluded inactives, so the inactive filter
is a *verified no-op here*, not an unimplemented one. It is applied regardless
and its count recorded, so a frame that does carry inactives needs no code
change. The non-starter QBs it does remove are the population behind the
backup-QB valuation defect: 45 of them project at mean **1.58**, and a
relaxed-construction arm is precisely what would reach for them.

## 3. Mechanics: same worlds, same order, zero LEV

Both arms received one `world_order_override` computed once on the shared
eligible frame. Ordinary boom visits `order[0:40]`; the exploration profile is
`start=0, count=40`, so it visits **the same forty worlds** — verified equal in
the receipts (frame 1 begins 1502, 2948, 3123, 3522…).

`existing=` was **not** passed between arms, per the assignment. Passing control
as `existing` would delete from treatment every candidate the control already
found — the shared core — and make the sleeve look far more novel than it is.
The union is computed afterwards.

| | frame 1 control | frame 1 sleeve | frame 2 control | frame 2 sleeve |
|---|---|---|---|---|
| attempted | 40 | 40 | 40 | 40 |
| new | 40 | 40 | 40 | 40 |
| duplicate / infeasible / error | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| legality + QB-safe passed | 40/40 | 40/40 | 40/40 | 40/40 |
| elapsed | 3.27 s | **2.09 s** | 3.26 s | **1.90 s** |

## 4. What replicates

**The sleeve changes construction almost completely.** On identical worlds and
identical draws:

| | frame 1 | frame 2 |
|---|---|---|
| shared rosters | **0 of 40** | **2 of 40** |
| union | 80 | 78 |

That is the pilot's purpose and it is answered: the relaxation is not cosmetic.
It is a different construction, not a perturbation of the same one.

Also replicating: **the sleeve solves ~40% faster** (fewer binding constraints),
produces **no infeasible or error solves**, passes legality and the QB-safe gate
100% on both frames, and uses slightly **fewer distinct players** (119 vs 127;
125 vs 129).

## 5. What does NOT replicate — pair support

| | frame 1 control → sleeve | frame 2 control → sleeve |
|---|---|---|
| distinct pairs | 1194 → **1253** (+4.9%) | 1232 → **1219** (−1.1%) |
| share of achievable | 0.829 → **0.870** | 0.856 → **0.847** |
| partner coverage, median | 0.119 → **0.170** | 0.117 → **0.129** |
| partner coverage, max | 0.651 → **0.492** | 0.578 → **0.661** |

On frame 1 the sleeve looks like it spreads pairing more evenly — more pairs, a
higher share of achievable, median coverage up 42%, and peak concentration
**down**. On frame 2 three of those four reverse: fewer pairs, a lower share,
and peak concentration **up**.

**So we are not claiming a coverage effect.** One frame would have supported an
attractive story about reduced concentration of the same low-value pairs — the
secondary criterion in your generator-arm plan — and the second frame refutes
it. Two frames at 40 solves cannot separate a construction effect from
slate-to-slate variation in pair structure. This needs many more frames, or many
more solves per frame, before it means anything.

## 6. Cost estimate for a larger run

Per-solve cost is linear in BOOM and cheap: **0.082 s/solve control, 0.052 s/solve
sleeve**. Fixed cost is the simulation, ~29.5 s for 389 × 10,000.

So a 12,800-solve BOOM-only ladder is roughly **17 minutes control / 11 minutes
sleeve**, plus one simulation. The expensive part of the real ladder is not here:
LEV is excluded by design, and its cost scales roughly n^2.5, which is what makes
D12800 a ~10-hour job. **A BOOM-only sweep across many frames is affordable**, and
given §5 that is the sweep the pair-support question actually needs — breadth of
frames, not depth of solves on one.

## 7. Boundaries

- No outcomes, no selection, no efficacy. `outcomes_read: false` in both receipts.
- The eligible universe differs from the production run's universe (we removed
  47/46 non-starter QBs), so these candidate sets are **not** a replication of the
  delivered Week-2 book and should not be compared to it.
- `mean25` is absent from both frames, independently confirming that view 3 of
  the forecast arm has no input on this data. Your fail-closed decision is right.
- Per your note, the p90 blend is kept entirely out of this pilot.
