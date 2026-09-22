# Laptop review item 3: the cap effect, isolated

Answering item 3 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Compare caps using the SAME selector objective, eligible pool, statuses, K and
> contest assignment. Mean-sort with caps versus delivered dual Emax changes more
> than exposure policy. The present result is exploratory, not an isolated cap
> effect.

**You were right, and the confound was larger than either of us assumed.** The
post-mortem compared a mean-sorted 25%-capped book against the *entered* book and
reported the cap as worth +1.3 mean. Isolated properly, the cap is worth **+11.3
mean and +26.6 best** under the delivered objective, and the objective swap was
costing back almost all of it. The two effects had opposite signs, which is
exactly why the confounded number looked negligible.

Everything below holds the pool (12,555 candidates), the statuses, K=97, the
contest assignment and the objective fixed, and varies only the cap.

## 1. Reproduction gate — passed before any arm was run

The archived run directory retains both player-world banks
(`incumbent_player_scores.npy`, `corrected_hsim_player_scores.npy`, 429 x 10,000
each), so the delivered selection is reconstructible rather than approximated.
Both sidecars were sha256-checked against `receipt.json` before use.

- Rebuilt `T = candidate_matrix(fr, cands, sel_draws)` and `Tv` from the rosters.
  `T.mean(axis=1)` reproduces `candidates.parquet:sel_mean` to **3.1e-5** — the
  roster-to-row mapping is right.
- Re-ran the delivered objective (`select_expected_max` on the equal-mass
  concatenation, K=97) as exact lazy greedy. It returns **all 97 delivered
  candidates in the exact delivered order**.
- Per-player realized points were derived independently from the standings
  exports; the resulting per-candidate realized reproduces the post-mortem
  receipt's `realized` column **exactly on all 12,555** (max abs diff 0.0000).

Without that first bullet nothing here would be worth reading, so it is the gate:
if the uncapped arm had not reproduced the delivered book, no capped arm computed
from these matrices could claim to isolate anything.

## 2. The isolated sweep

Uniform per-player cap as a share of the 97-row book. `proposal` is study 5 of the
post-mortem as written (Doubtful 0, Questionable-with-a-prop 10%, Questionable-with-no-prop
5%, DST 20%, everyone else 30%).

| objective | cap | max exp | realized mean | realized best | >=150 | >=170 |
|---|---|---:|---:|---:|---:|---:|
| **dual_emax (delivered)** | **none** | **51** | **98.40** | **157.96** | **3** | **0** |
| dual_emax | 40% | 38 | 102.98 | 184.54 | 5 | 1 |
| dual_emax | 35% | 33 | 105.99 | 184.54 | 5 | 1 |
| dual_emax | 30% | 29 | 108.56 | 184.54 | 7 | 1 |
| dual_emax | 25% | 24 | 109.75 | 184.54 | 9 | 1 |
| dual_emax | 20% | 19 | 113.53 | 184.54 | 10 | 1 |
| dual_emax | 15% | 14 | 113.44 | 184.54 | 7 | 1 |
| dual_emax | proposal | 29 | **114.68** | 184.54 | 9 | 2 |
| mean_greedy | none | 97 | 70.99 | 109.70 | 0 | 0 |
| mean_greedy | 25% | 24 | 106.89 | 183.56 | 8 | 1 |
| mean_greedy | proposal | 29 | 111.84 | 183.56 | 6 | 1 |

The post-mortem's mean-sorted figures reproduce: it reported no-cap 71.0 / 109.7 / 0
(here 70.99 / 109.70 / 0, exact) and cap-25% 106.3 / 183.6 / 8 (here 106.89 / 183.56 / 8;
the 0.6 of mean is a tie-break difference, the shape is identical).

**The sign is uniform across all seven cap levels and both objectives.** No level
had to be picked to see it. The *level* is not identified by one slate and should
not be read off this table.

## 3. What the cap costs in the selector's own currency

This is the part that does not depend on the outcome, and it is the number I would
actually put in front of a decision. A cap can only lower E[max] — it is a
constraint on the same greedy — so its ex-ante price is exactly measurable:

| arm | sim E[max] | sim P(>=194) | cost vs delivered | realized best |
|---|---:|---:|---:|---:|
| dual_emax, no cap (delivered) | 203.45 | 0.6460 | — | 157.96 |
| dual_emax, 30% | 202.46 | 0.6321 | **-0.99 (-0.5%)** | 184.54 |
| dual_emax, 25% | 201.75 | 0.6190 | **-1.70 (-0.8%)** | 184.54 |
| dual_emax, 20% | 200.92 | 0.6036 | -2.53 (-1.2%) | 184.54 |
| dual_emax, proposal | 198.73 | 0.5667 | -4.72 (-2.3%) | 184.54 |
| mean_greedy, no cap | 181.68 | 0.2994 | **-21.77 (-10.7%)** | 109.70 |

**A 25% cap costs 0.8% of the selector's own objective. Switching to mean-sort cost
10.7% — thirteen times as much.** That is the whole confound in one line: the
post-mortem's comparison bundled a nearly-free constraint with a very expensive
objective change, and on this slate the two pointed opposite ways.

## 4. Mechanism, and the honest limit on it

The realized mean change decomposes exactly into exposure-delta x realized-points
(the terms sum to 11.34, which is the observed delta). Delivered -> 25% cap:

| cut | from | to | scored | | added | from | to | scored |
|---|---:|---:|---:|---|---|---:|---:|---:|
| Justin Jefferson | 51 | 24 | 8.5 | | Jaxon Smith-Njigba | 5 | 13 | 45.5 |
| Bijan Robinson | 42 | 24 | 11.1 | | CeeDee Lamb | 8 | 13 | 38.3 |
| 49ers DST | 36 | 24 | 8.0 | | Ja'Marr Chase | 10 | 14 | 26.5 |
| Dalton Schultz | 24 | 19 | 29.0 | | Panthers DST | 0 | 4 | 26.0 |

The cap does not know who will bust. It converts concentration into breadth, and
on this slate breadth paid twice: the three most concentrated positions all busted,
and the forced spillover happened to reach the slate's three biggest scores. **Both
halves of that are outcome-dependent and neither generalizes from n=1.**

What does carry over is the conditional: a cap is a hedge against the selector's
concentration being uninformative, and Week 2 measured that concentration as
*anti*-informative — pool corr(sel_mean, realized) = -0.49, and the simulated
P(>=194) deciles were monotonically inverted against realized score. The cap is
insurance against the exact failure mode already on the record, and section 3
prices the premium at under 1%.

For scale: the pool oracle is **197.26** and the whole 12,555-candidate pool holds
exactly **one** row at >=194. The delivered book reached 157.96, the capped book
184.54 — the cap closed **68% of the available selection gap** on this slate.
Neither book contained the oracle lineup.

## 5. Feasibility, and where the cap starts to bind

- At **15%** (14 rows) the constrained greedy **cannot fill the book**: 91 of 97
  under dual_emax, 87 under mean_greedy. The pool itself is too concentrated. I
  report the greedy-feasible count, not a proof of infeasibility — a smarter
  assignment might fill 97, but the delivered chain uses greedy.
- At **25% the first 33 book positions are unchanged** — milly, flea, huddle,
  nickel, pylon and satellite receive byte-identical rosters. The cap does not
  bind until deep in the greedy and only reshapes the tail of the book. The 184.54
  lands in supersat1c.
- The **tiered proposal binds at rank 1** (Doubtful -> 0 removes players
  immediately) and moves the Millionaire entry 82.62 -> 91.78. Only 27 of 97
  delivered rows survive it, against 51 under a flat 25%.

## 6. Two parts of the proposal that are not implementable as written

1. **The >=30% field-ownership exemption is not computable.** This build had no
   ownership source at all (`proj_tourney.fallback_reason = "no ownership source
   available on this build"`). Any exemption keyed to projected field ownership
   is unavailable pre-lock until an ownership input is restored, and using
   realized `pct_drafted` would be leakage. Excluded here.
2. **"<=20% of the majors' rows" is not a book-level cap** — it needs per-contest
   counting inside the selection loop, which the current selector has no notion of.
   Excluded here; it needs a design decision, not a threshold.

## 7. What I am claiming and what I am not

Claimed: the cap effect is now isolated, the confound you named is real and was
larger than the reported effect, and the cap's ex-ante cost in the selector's own
objective is under 1% at 25%.

Not claimed: that caps help in general, or that any particular level is right.
One slate, outcomes already observed. Picking 20% over 30% off this table would be
panel mining and I am not proposing it.

Reproduce: `reports/item3-cap-isolation/` — `build_matrices.py` (sha-gated rebuild),
`reproduce.py` (the gate), `actuals.py`, `sweep.py`, `objective.py`, `mechanism.py`,
plus the three result CSVs. Reads only from the clean release worktree at 2dc116c.

## 8. Mutation check

Three deliberate breaks, to prove the instrument can fail:

| mutation | expected | observed |
|---|---|---|
| cap set to 97 (cannot bind) | returns the delivered book exactly | **exact match** |
| roster-to-row mapping corrupted | reproduction gate fails | **sel_mean off by 24.8, book mismatch** |
| cap set to 24 (binds) | book must change | **changed, 51/97 overlap** |

The second is the one that matters: a gate that cannot fail proves nothing, and
this one fails loudly on exactly the error that would invalidate every arm.
