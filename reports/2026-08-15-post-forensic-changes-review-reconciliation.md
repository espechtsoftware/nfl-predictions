# Post-forensic changes review reconciliation

Date: 2026-08-15 08:24 CDT  
Status: pre-outcome design reconciliation; no production promotion

## Disposition

All five suggestions in `2026-08-15-post-forensic-changes-review.md` are
accepted, with one precision caveat: a late/unlocked player missing from exact
P is timing-reachable, not necessarily roster-reachable. Salary, position,
stack and retained-candidate rules can still block that move.

The review arrived while the scorer reconciliation, realistic-recourse
proposal ledger and realistic-recourse result objects were all absent. The
in-flight validation build was canceled before it could license an execution.
This makes the changes pre-outcome protocol work rather than a post-result
choice.

## Changes to realistic recourse

The registered protocol now requires three extra cuts while leaving
`prospective-recourse-policy-v1` unchanged:

1. Freeze `naive-mean-reoptimization-v1` beside the treatment. It greedily
   selects the highest conditional projected-mean retained candidate under
   identical locks, with no liveness or book-tail objective. The result will
   report hindsight, realistic and naive weekly maxima/tails, plus the
   realistic-minus-naive gap.
2. Preserve all 80 pre-outcome simulated 194-reach probabilities and their
   alive/marginal/effectively-dead classes. Report the per-slate profile and
   its descriptive association with realistic gain and realistic-minus-naive
   gain.
3. Partition players missing from exact P into locked and unlocked at 3:55 PM
   Eastern, both overall and by the immutable first-failed layer at 210.

Implementation review also caught a separate defect: exact P was being looked
up as the best generated candidate even though it is an oracle over generated
player support. The runner now reconstructs exact P from authoritative player
outcomes only after both proposal books are create-only frozen, under the
exact $49,000 floor, $50,000 cap, QB+2 and one-bring-back contract. Its score
must reproduce the immutable exact-stack result to 1e-6. Outcomes never enter
either proposal.

## SIS player-grain next protocol

The prior remains explicitly low: a better denominator does not cure the
failed marginal insertion channel. The player-grain pass licenses only a
receiver-specific copula/dependence mechanism; it does not license another
marginal feature.

The next protocol must:

- generate a fresh repaired-path G0/G1 control receipt from code descended
  from `26e73c5`; no pre-repair numeric reference may be inherited;
- use two-sided absolute-log error for QB-WR, QB-TE, WR-WR, RB-RB and the
  supported aggregate cells;
- report multiplicity `>=2`, `>=3` and `>=4`, with `>=4` mandatory but ungated
  when its support rule remains unmet;
- prevent improvement at QB-WR from passing if it worsens the already
  over-coupled multiplicity or teammate cells; and
- license at most a 2026 paired shadow, never retrospective promotion.

The current post-repair scorecard values visible inside the invalidated TD
runs are diagnostic only. They are not yet an accepted standalone reference;
the next protocol must reproduce and checksum its own untreated control before
fitting or evaluating the receiver-specific treatment.

## Candidate reallocation target

The fixed-budget construction shadow will not allocate by historical arm/tag
yield. Its target will be outcome-viewed structure from corrected exact P:
games spanned, largest team block, stack shape, positional spend and salary
distribution. Before choosing generator buckets, it must run a constraint-
attribution census: test whether exact P would remain feasible when each
production construction rule is imposed individually and in the registered
combinations.

This can identify an excluded structural region or a specific binding rule.
It remains hypothesis generation: exact historical P amounts cannot become
fitted generator weights, and any candidate reallocation stays fixed-budget
and prospective/shadow-only.

## Production consequence

None. The adopted exact-80 baseline and all production construction rules are
unchanged. These changes improve the interpretation and validity of the next
descriptive/prospective evidence.
