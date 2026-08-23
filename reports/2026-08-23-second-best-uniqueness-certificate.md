# Second-best uniqueness certificate — law change record

Date: 2026-08-23. Status: adopted in code at `2aba4ae` before any v7
lane launch; no batch artifact was ever produced under the old
certificate (v6 failed terminally; v7 namespaces were virgin).

## The proposition proven (unchanged)

For every (parameter-arm, world) cell, the engine must certify that the
legal roster maximizing the exact integer combined objective
`primary_micro * radix − rank_sum` is UNIQUE, with the complete matrix
of 7,000 cells per slate all-optimal or the task fails.

## Old certificate and why it died

Stage 2 froze `combined == optimum`, excluded the witness by no-good,
and demanded exact infeasibility. Proving emptiness at the pinned value
forces CBC to close the entire branch-and-bound tree with no bounding
help. Real-world consequence chain:

1. v6 task-0 lost exactly 7 of 7,000 cells to the 120 s deadline
   (terminal failure, `status_counts={'error': 7, 'optimal': 6993}`).
2. The 700-cell local probe of all seven failed ranges under a 600 s
   deadline: six cells complete in 77–155 s, but arm 5 visit 512 times
   out at 600 s.
3. A one-off measurement of that cell ran past **39 CPU-minutes without
   terminating** and was killed — per-cell deadlines cannot bound this
   formulation on pathological worlds, and 53 slates were unprobed.

## New certificate (mathematically identical census)

Stage 2 keeps ONLY the witness exclusion and maximizes the SAME combined
objective:

- OPTIMAL with runner-up combined `< optimum` (exact integer compare,
  value reconstructed from the decoded roster) ⇒ UNIQUE;
- INFEASIBLE (either CBC header: presolve `Infeasible` or
  branch-and-bound `Integer infeasible`) ⇒ the witness was the only
  legal roster ⇒ UNIQUE;
- runner-up `== optimum` ⇒ rank-sum collision ⇒ AMBIGUOUS (unchanged
  semantics);
- runner-up `> optimum` or any unclean terminal ⇒ ERROR (poison).

`max over (roster ≠ witness) of combined < combined(witness)` is exactly
the uniqueness proposition; only the certificate form changed, from a
tree-closure emptiness proof to a bound-prunable optimization.

## Measured effect (same real slate, same cells)

| cell | old form | new form |
|---|---|---|
| arm 5 visit 512 | ≥ 39 min, unterminated | 1.00 s |
| arm 0 visit 930 | ~155 s | 1.30 s |
| arm 2 visit 605 | ~137 s | 1.21 s |
| worst of 7 failed + 3 control cells | unbounded | **1.38 s** |

The engine test suite dropped from minutes to ~14 s. The 600 s deadline
(retained as a belt) now carries ~430× margin over the worst observed
real cell.

## Verifier symmetry

The independent verifier rebuilds the exclusion-only stage-2 model,
reads the certificate form from the retained receipt (optimal or
infeasible only), legality-audits the decoded runner-up, re-proves the
strict integer gap itself, and pins the stage witness hash to the
runner-up roster. Its solution parser also accepts CBC's
branch-and-bound infeasibility header — the same
misclassified-benign-terminal defect class that terminally failed the
v4 producer, swept into the verifier.

## Scientific impact statement

None on selection or scores: the certificate never touches draws,
objectives, dedup, admission, or selection; a cell either proves the
same unique optimum or fails closed. The change strictly enlarges the
set of worlds whose (identical) optimum can be certified within any
finite deadline.
