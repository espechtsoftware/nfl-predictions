# The dead lever and the measured failure are the same thing

`N_QB_VARIANTS` is an adopted lever that has never run on the money path
(`37c9fce3`). Read alongside this afternoon's retrieval diagnostic (`6dcf9fd7`), it stops
being an inert flag and becomes the most interesting item on the board.

## What N_QB_VARIANTS actually does

From `backtest/engine.py:2007–2035`. For each of the **top 8 QBs by simulated p90**, it
solves **4 lineups** (the default) that all **lock that QB** but are forced apart from one
another — `max_overlap=6`, so each variant differs from its siblings by at least three
players. That is 8 × 4 = **32 candidates whose only purpose is depth *within* a stack**:
same quarterback, different pass-catchers and different supporting cast.

The code's own motivation:

> *"the harvest attribution found the 40 entries spread over ~16 QBs with max 2-of-8 overlap
> vs the weekly optimal — **right stacks, wrong pieces**."*

Adoption evidence recorded in the same comment: ADOPTED 2026-08-04; QBVAR4 alone +2 tails
(25/107); with the ownership fade on, equal tails but **the best median of the programme
(14.6%) and two ≥237 weeks**.

## Why that matters today

The Week-2 retrieval diagnostic found, independently and without knowing any of the above:

- the pool held 30 lineups ≥170 and the book entered **none**;
- the best candidate (197.26) sat **5 swaps of 9** from the nearest entered lineup;
- **8 of its 9 players were already rostered somewhere in the book.**

That is *right stacks, wrong pieces*, measured on a live 2026 slate — the same sentence the
lever was adopted to address in August, arrived at from the opposite direction.

**So the adopted-but-never-run lever targets precisely the failure mode I measured.** I did
not go looking for that; the lever audit and the retrieval diagnostic were separate tasks
and met in the middle.

## What I am *not* claiming

- **Not that restoring it would have recovered the 39.3 points.** `qb_variant` adds
  *candidates*, and my own diagnostic says Week 2's gap was retrieval, not supply — the
  lineup already existed and was not selected. Adding 32 more candidates does not fix a
  selector that mis-ranks the ones it has. If anything, the diagnostic argues the opposite.
- **Not that the August evidence transfers.** It was measured inside the `nfl_dfs` replay
  engine, and the money path is nfl2 — the post-selection law says a verdict does not carry
  across a changed downstream stage, and this is a changed *repository*.
- **Not that it is cheap.** The lever audit priced it as **high**: nfl2 has no qb-variant
  construction at all, so this is porting a generation family, not flipping a flag.

## The honest reading

Two independent findings point at the same mechanism from opposite ends, which is unusual
enough to be worth naming. But they point in **opposite directions on what to do**: the
August adoption says add stack depth; the Week-2 diagnostic says the binding constraint was
selection, not supply.

**Both can be true.** Depth within a stack only pays if the selector can then tell which
variant is the good one — and the measured fact is that it cannot, because the simulated
tail is anti-ranked against realized outcomes. That ordering makes the sequence clear:

1. **Find out whether Week 1 looks like Week 2** (one tool run, blocked only on the
   Week-1 candidate file, `7c9de246`). If retrieval is the constraint on both slates, then
   every supply lever — `qb_variant` included — is improving the half that is not broken.
2. **Only then** decide whether `qb_variant` is worth porting.

Striking it from the adopted stack would also be defensible, and is the cheaper honest
option: a lever listed as adopted in `CLAUDE.md` that has never executed on the money path
is a claim the code does not support. Either port it or stop calling it adopted — the
current state is the one that should not persist.
