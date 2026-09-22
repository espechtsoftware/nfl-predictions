# Exposure caps: `Doubtful -> 0%` and per-contest counting, implemented and in the chain

Operator authorisation 2026-09-21 ("do as you suggest") for the two changes recommended
in [item 5](2026-09-21-laptop-item5-injured-concentration.md): cap Doubtful players at
zero rows, and count contest membership inside the selection loop rather than after it.

`scripts/exposure_cap_book.py`, wired into `scripts/sunday_build_host.sh` as step 6.
**It enters nothing.** It writes a book, an exposure sheet and a receipt for the operator
to read before upload — the same status as vetting and composite.

## 1. Why it is a tool and not a patch to the selector

The book is produced by the lab's `live_week.py`; nothing of ours modifies nfl2. But the
Week-2 archive showed the run directory already carries everything needed to redo the
selection ourselves: the candidate pool, the frame, and both player-world banks under
`--emit-a5-sidecars`. So this re-runs **the delivered objective** — greedy expected weekly
maximum over the equal-mass concatenation of the incumbent and corrected-hsim banks — from
**the delivered pool** at **the delivered K**, with the caps as the only difference.

That construction is not assumed to be faithful, it is **checked**: in item 3 it returned
all 97 delivered Week-2 lineups in the exact delivered order, and a test here pins the
uncapped path against a plainly-written reference greedy.

`--emit-a5-sidecars` is already passed by `sunday_build_host.sh`, so Week 3 will have the
banks. **If they are ever absent the tool errors** naming them, rather than silently
falling back to a different objective, which would make the arms incomparable.

## 2. What the caps are

| cap | default | note |
|---|---|---|
| **Doubtful** | **0% of the book** | needs no forecast and no threshold — it reads a designation already in the frame |
| Questionable | 10% | |
| any player | 30% | item 5 showed the injury rule *alone* raises peak exposure 51 -> 57; it needs this beside it |
| any DST | 20% | |
| **any one contest** | **50% of that contest's rows** | counted *inside* the selection loop |

The per-contest default is deliberately weak. It stops the pathological case — a player in
20 of 23 rows of one contest — without picking a tight level off a single slate, which
would be exactly the panel mining I declined to do in item 3.

## 3. Per-contest counting, and why it had to be inside the loop

Item 5's finding: a share-of-book cap constrains *how many* rows hold a player, never
*which*. Capping McConkey from 26 rows to 4 moved one of the four **into the Millionaire
seat**, which the delivered book had kept him out of.

Contest membership is a property of a book *position*, and both layouts assign contests by
position — `sequential` gives each contest a disjoint slice, `top` gives every contest
ranks 1..N, so early positions sit in many contests at once. The tool builds that map and
checks it as each seat is filled.

**A limitation I am stating rather than hiding:** selection fills positions in order, so a
tight per-contest cap can dead-end even when some valid assignment exists. When that
happens the tool **refuses and names the position it stuck on**. It never emits a book
that breaches a cap, and never a short one.

## 4. Verified on real data

Recomputed against the archived Week-2 run directory (K=97, the Week-2 contest layout):

| | delivered | capped |
|---|---:|---:|
| simulated E[max] | 203.45 | 198.12 (cost **2.62%**) |
| peak exposure | 51 rows | 22 rows |
| **Zay Flowers (Doubtful)** | **48 rows** | **0** |
| Tua Tagovailoa (Doubtful) | 5 rows | 0 |
| Ladd McConkey (Questionable) | 26 rows | 9 |
| realized mean | 98.40 | **114.28** |
| realized best | 157.96 | **184.54** |
| contests improved | — | **10 of 12** |

The realized columns are retrospective and prove nothing on their own; the E[max] cost and
the exposure columns are the decision-relevant part.

## 5. Week-3 preflight — the question that mattered

Week 3 is 198 entries across 40 contests under `ENTER_LAYOUT=sequential`, a much harder
packing problem than Week 2's 97 across 12. Run against the Week-3 `contests.json` on the
Week-2 pool, to find a dead-end **now** rather than on Sunday morning:

| contest cap | fills 198? | E[max] | cost | peak exposure |
|---|---|---:|---:|---:|
| 50% | **yes** | 208.35 -> 204.26 | 2.0% | 99 -> 59 rows |
| 34% | **yes** | 208.35 -> 204.16 | 2.0% | 99 -> 59 rows |
| 25% | **yes** | 208.35 -> 203.96 | 2.1% | 99 -> 54 rows |

Feasible at every level, and cheap. Two things worth knowing:

- The uncapped book puts one player in **99 of 198 rows** — exactly 50%, the same
  concentration shape as Week 2's 51 of 97.
- At this entry spread the **global 30% cap does the work** and the per-contest cap is
  nearly free insurance: peak exposure is 59 at both 50% and 34%, because 30% of 198 is 59.
- The nineteen 1-entry `sat20` contests cannot be constrained by any per-contest cap — a
  single row is 100% of its contest by definition. They are named in the receipt
  (`sat20 x19`) rather than passed over in silence. The cap does real work only on the
  larger blocks: `supersat25lo` (20 rows), `supersat25hi` (17), `supersat2` (5), `ffwc` (4).
- The per-contest cap is not free in *time*: at 25% the selection logged 354,360 position
  deferrals against 43,310 at 50%. It completes, but a tighter level costs Sunday minutes.

## 6. Tests

13 tests, added to the money lane. The load-bearing ones:

- the uncapped path reproduces a plainly-written reference greedy exactly
- a Doubtful player takes zero rows — **and** a companion test proves he is otherwise
  attractive enough to be selected, so the first test cannot pass vacuously
- no player exceeds the per-contest cap in any contest — **and** a companion test proves
  the uncapped run breaches it, so the cap is not being tested against a pool that never
  reaches it
- missing banks, a bank that does not match the receipt, and a roster-to-player mapping
  drift each fail closed
- caps that cannot fill the book fail rather than emit a short one
- a dead-ended per-contest cap names the position

**Mutation check** — four guarantees broken in the code, each caught:

| mutation | result |
|---|---|
| Doubtful cap ignored | caught |
| per-contest counting removed | caught |
| sidecar sha256 check removed | caught |
| short book emitted silently | caught |

## 7. What is still the operator's call

The tool emits; it does not enter. Whether Sunday's upload comes from the vetted book or
the capped book is a decision for the sheet, not for me. The cap *levels* are defaults, not
findings — item 3 established the sign of the cap effect across every level tested, never a
level.

Reproduce: `reports/exposure-cap-preflight/` holds the recomputed Week-2 sheet and the
three Week-3-layout receipts. `contests.json` itself is the stake plan and is never
committed.
