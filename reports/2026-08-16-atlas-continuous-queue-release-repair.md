# ATLAS continuous-parity queue-release implementation repair

Date frozen: 2026-08-16, while the binary 32-GiB full-cell preflight was
nonterminal, before repair5 was licensed/launched and before any continuous
parity result.

Applies to `20260816-atlas-interaction-parity-v1`.

## Defect

The frozen parity protocol says the diagnostic remains deferred while the
binary preflight and repair5 have priority. If the preflight fails, parity is
next; if the preflight succeeds, parity remains deferred until repair5 releases
research capacity.

The first launcher implemented only the direct failed-preflight branch. If the
preflight succeeded but the 54-cell repair5 population later failed, the
launcher would reject even after every repair5 cell was terminal. That is
narrower than the frozen queue and would strand the continuous formulation
without a test.

## Sole repair

Keep the immutable image, injected diagnostic source, real-slate cell,
resources, binary-versus-continuous calculations and parity gate unchanged.
Permit launch under exactly either of these score-free queue triggers:

1. the strict 32-GiB preflight completion records terminal failure; or
2. the preflight succeeded, repair5 then reached all 54 terminal cells with at
   least one failure, and the separately frozen metadata-only repair5 terminal
   census records `continuous_parity_capacity_released=true` while retaining
   `scientific_result_valid=false`, `effect_fields_inspected=false` and
   `historical_scoring_licensed=false`.

A successful repair5 strict harvest does not trigger this fallback; its frozen
historical-score path retains priority. Nonterminal, missing, mixed or
cancelled repair5 evidence fails closed. The parity manifest and strict
finisher must bind whichever exact trigger licensed the run, including the
repair5 census/completion hashes for branch 2.

This is an implementation/queue correction only. It changes no scientific
question, data, roster, outcome, threshold or production consequence.
