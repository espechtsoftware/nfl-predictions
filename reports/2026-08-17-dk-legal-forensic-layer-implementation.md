# DraftKings-legal forensic layer implementation

Date: 2026-08-17

Status: implemented and fixture-validated; no historical/cloud execution and
no production change.

## 2026-08-30 erratum

The implementation described below originally treated two represented games
as DraftKings platform legality. DraftKings Classic instead requires players
from at least two teams; the nine-player roster plus eight-per-team cap already
enforces that condition. Any earlier `H_DK_legal` output from the v1 code used
an extra two-game house rule and is superseded as platform-only evidence. The
corrected legal oracle uses `minimum_games=1`; historical construction layers
continue to receipt `minimum_games=2` when that strategy is intended. A prior
score must be recomputed before it is cited as the true DraftKings-only ceiling.

This additive diagnostic implements the layer requested by
`2026-08-17-extreme-tail-review-reconciliation-and-queue-amendment.md`:

The additive core decomposition is:

`H_DK_legal -> H_strategy -> P -> C -> S`

Its strategy attribution is deliberately expanded rather than assigning the
whole first gap to stacks or anti-correlation:

`H_DK_legal -> H_no_salary_floor -> H_strategy`

The first step measures all non-salary strategy constraints together. The
second step isolates the `$49,000` floor conditional on those other strategy
constraints. This attribution layer does not replace or reorder legacy
H/P/C/S.

## Exact boundary

`H_DK_legal` maximizes realized lineup score while enforcing only the hard
DraftKings NFL Classic feasibility contract represented in this repository:

- nine unique players with `1 QB`, `2--3 RB`, `3--4 WR`, `1--2 TE`, and
  `1 DST`;
- salary at or below `$50,000`;
- no more than eight players from one team (therefore at least two teams).

It does **not** enforce the production `$49,000` salary floor, QB+2 stack,
one bring-back, same-team-RB prohibition, or RB-versus-DST prohibition. Those
are construction-strategy rules and remain on the `H_strategy` side.

`H_strategy` is an explicit alias of the existing `H` result. The legacy `H`
key is retained unchanged, as are `P`, `C`, `S`, the exact three-field
`gaps` object (player support, construction and selection), and the existing
`first_failed_layer` classification. New consumers receive a separate
`strategy_gaps` object and `first_failed_layer_extended`; no old gap or
failure label is rewritten.

`H_no_salary_floor` is also retained. It remains the conditional diagnostic
that removes only the salary floor while holding the other strategy rules
fixed; it is not relabeled as DraftKings-only legality. The new strategy
object reports all three quantities explicitly:

- `H_DK_legal - H_no_salary_floor`: non-salary strategy constraints;
- `H_no_salary_floor - H_strategy`: the salary floor conditional on the other
  strategy constraints; and
- `H_DK_legal - H_strategy`: their combined ceiling difference.

## Surfaces

- `final_forensic.decompose_slate` adds the two explicit layers, policy
  receipts, strategy gap, and extended threshold attribution.
- `final_forensic_outputs` includes the additive layers in player-capture and
  oracle-roster warehouse frames when present, while retaining compatibility
  with previously materialized five-layer inputs.
- The frozen oracle-roster warehouse schema is intentionally not widened.
  Its three gap columns retain their legacy H-to-P, P-to-C and C-to-S meaning;
  the new strategy gaps live in the analysis JSON/addendum surfaces.
- The forensic runner aggregates the added layers and gap without removing or
  renaming legacy fields.
- The corrected exact-stack addendum reports distinct core and strategy-
  attribution layer orders, a dedicated descriptive DK-legality/strategy
  section, changed-roster count, tail counts and extended first-failure
  counts.

## Use restriction

The optimizer sees realized player scores, so this is a perfect-hindsight
descriptive ceiling. A positive `H_DK_legal - H_strategy` gap may motivate a
prospectively frozen exception-sleeve hypothesis, but it cannot promote a
relaxed strategy, revise a historical arm verdict, or alter the money policy.

No ATLAS artifact, partial treatment output, new historical `H_DK_legal`
result, cloud job or production path was opened or changed while implementing
this layer.
Any future forensic population will perform one additional deterministic CBC
solve per slate; that runtime increase has not yet been measured on a full
historical panel.

## Fixture validation

Focused tests establish that:

- DK-only fixtures below the production salary floor and without a stack or
  bring-back, including same-team RBs facing the selected DST, are admitted,
  while an over-cap variant remains infeasible;
- a DK-legal roster containing same-team running backs and no production
  bring-back is admitted by `H_DK_legal` and rejected by `H_strategy`;
- `H_strategy` is exactly equal to the existing `H` object;
- existing H/P/C/S scores and legacy gap fields remain unchanged;
- the old `first_failed_layer` value remains unchanged while the extended
  classification attributes a newly reachable threshold to strategy;
- old five-layer report fixtures remain accepted; and
- new seven-layer player-capture and warehouse outputs retain all legacy
  fields and add the two explicit layers.

Validation command:

```text
.venv/bin/pytest -q tests/test_final_forensic.py \
  tests/test_final_forensic_cleanup.py \
  tests/test_final_forensic_corpus.py \
  tests/test_final_forensic_diagnostics.py \
  tests/test_final_forensic_outputs.py \
  tests/test_post_forensic_construction.py \
  tests/test_final_forensic_hpcs.py \
  tests/test_exact_p_identity_source.py \
  tests/test_exact_p_generator_census.py \
  tests/test_cbwu_oi_construction_diagnostic.py
```

Result: `56 passed`. Python compilation and `git diff --check` also pass.
