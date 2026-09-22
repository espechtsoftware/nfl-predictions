# Questions for the lab: exposure caps, and what they do to the prospective gates

Production has implemented and wired in `scripts/exposure_cap_book.py` (see
[the implementation report](2026-09-21-exposure-caps-implemented.md)). It re-selects from
the run directory with the delivered objective under explicit caps, emits a book and an
exposure sheet, and **enters nothing**. Three questions are yours, not ours.

Context: Week 2 entered Zay Flowers — listed **Doubtful** at build time — in 48 of 97 rows
including the Millionaire seat. He scored 0.0. The operator authorised `Doubtful -> 0%` and
per-contest counting on 2026-09-21.

## 1. The one that actually worries me: do the pre-lock captures still measure the book?

`ordering_shadows.py` and the other outcome-blind captures run against `$K90_DIR` — the
**selector's** book — not against what is uploaded. That has been harmless because they were
the same thing modulo vetting. **If the operator uploads the capped book, every prospective
gate is grading a book we did not enter.**

We have a standing rule that a paused gate silently loses graded weeks; a *mis-aimed* one
seems worse, because it keeps producing numbers. Do you want:

- **(a)** the shadows recomputed against whichever book is actually entered, or
- **(b)** the shadows left on the selector book and the capped book treated as a separate,
  separately-graded arm, or
- **(c)** caps held out of Week 3 entirely so the gates stay comparable?

We have no view we would defend here. It is your protocol.

## 2. Should the caps live in `live_week.py` instead?

Ours is a post-hoc re-selection because **nothing of ours modifies nfl2**. It is faithful —
it reproduced all 97 delivered Week-2 lineups in the exact delivered order — but it is a
second selection pass rather than a constrained first one. If you would rather the caps sat
inside the selector, say so and we will send a patch plus a failing test under
`reports/lab-handoffs/` and leave the branch decision to you.

## 3. The per-contest level

Defaulted to **50% of any one contest's rows** — deliberately weak, because item 3
established only the *sign* of the cap effect across every level tested, never a level, and
choosing one off a single slate is panel mining.

Week-3 preflight (198 entries / 40 contests, run on the Week-2 pool) is feasible at 50%,
34% and 25%, costing 2.0–2.1% of E[max]. Note two things:

- the **global 30% cap does the work** at this entry spread — peak exposure is 59 rows at
  both 50% and 34%, because 30% of 198 is 59;
- tightening is not free in wall-clock: 43,310 position deferrals at 50% against **354,360**
  at 25%.

If you have a preregistered view on exposure levels we will take it. Otherwise we will run
the default and record it as a disclosed choice rather than a finding.

## Not asking

The `Doubtful -> 0%` rule itself. It reads a designation already in the frame, needs no
forecast and no threshold, and the operator has authorised it. We are telling you, not
asking.
