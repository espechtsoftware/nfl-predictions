# Production-law dependence source-population amendment

Date frozen: 2026-08-17, before any source-lock object, outcome query or
remeasurement result existed.

Amends only the eligible player source in
`2026-08-17-production-law-dependence-remeasurement-protocol.md`.

## Outcome-free preflight finding

The R0 acquisition catalog contains 29,605 season/week/player rows and no
duplicates across the exact 54-slate grid, but it is deliberately broader than
the players used by the money candidate generator. The unfiltered >=4 skill-
position population is 21,799 rows and includes, for example, 93 QBs in 2023
Week 1. The acquisition panels also set `research_eligible=false` on every row,
so that legacy flag cannot recover the comparable active/relevant population.

No outcome, candidate score, lineup score, rank, ownership or treatment effect
was read in making this finding.

## Corrected population

The canonical population is now:

1. the exact union of player IDs appearing in at least one native candidate
   across R0--R4 on that season/week;
2. restricted to QB, RB, WR or TE; and
3. restricted to locked served mean projection >=4.0.

The exact outcome-free preflight contains 68,199 native candidate rows,
10,729 season/week/player appearances in their five-block union and 9,469
rows after the position/mean restriction. These counts are frozen mechanical
invariants, not results.

The source-lock query may therefore additionally read only `panel_run_id`,
`season`, `week`, `cand_ix`, `players`, `score_artifact_uri` and
`score_artifact_sha256` from the immutable candidate staging panels. It must:

- apply the registered R3/2025 Week 1 repair-panel substitution;
- reproduce exactly 68,199 rows and the complete 54 x 5 panel grid;
- require contiguous candidate indices within every panel/slate;
- require exactly nine distinct IDs per roster;
- match every ordinary panel/slate URI and SHA to the already locked transfer
  artifact; for the registered R3/2025 Week 1 substitution, require the exact
  repaired URI in the validated repair completion receipt and require its SHA
  to equal both the validated repaired SHA and the original locked transfer
  artifact SHA (the repair already proved the two objects byte-identical); and
  and
- fail if any union player is absent from the canonical R0 player catalog.

The source lock persists only the candidate-union catalog rows, their hash, the
three frozen counts above and the explicit byte-identical repair-substitution
receipt. The outcome runner does not query candidate membership again.

All q90 definitions, nine G0 cells, support rules, aggregate/3-of-5 premise
gate, outcome firewall and consequence boundary remain unchanged.
