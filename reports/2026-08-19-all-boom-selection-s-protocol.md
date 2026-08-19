# All-boom selection follow-up (S endpoint) — FROZEN 2026-08-19

**Protocol id:** `20260819-all-boom-selection-s-v1`. Licensed by the C
arm's preregistered rule: "S requires its own frozen follow-up only if C
improves" — C improved (+9.06 mean, 43/54, co-primary p ≈ 0). One shot;
54 cells; the operator's ask is explicit: boom as ACTUAL LINEUPS against
the full valid history (the 54-slate 2023–2025 corpus; 2019–2022 requires
the corrected-universe rebuild, queue item A10).

## Question

The C arm proved the boom-deep pool has a higher ceiling at the exact
registered budget. Does the UNCHANGED production selector convert any of
it into the actual 80-entry book? Predeclared prior:
`favorable-c-cleared-s-uncertain` — the corpus C−S gap is ~5 points, the
treatment's deduplicated union doubles (order-statistic help), but prior
arms have repeatedly improved pools without moving selected books.

## Arms (both rebuilt per slate, per seed pair)

- **Control:** the ATLAS C control path verbatim — dose-zero regeneration
  plus verbatim role injection, gated by exact source reproduction
  against the registered natives (`base._reproduction_check`).
- **Treatment:** the all-boom C path verbatim — `CAND_MULT=0`,
  `N_BOOM=200`, `BOOM_UNIQUE_FILL=1`; truncation to the native non-role
  count; role natives appended with artifact totals; candidate budgets
  asserted equal per seed.
- **Selection (identical for both):** `combine_cbwu_books` five-book
  union at the fixed budget, `select_tail_entries` exact-80 at line 194,
  `SELECT_LSE=0` — the unchanged production selector. The four-seed
  recovery slate (2025 W1) has no S by design; 53 paired S slates.

## Cross-run binding gates (fail closed per cell)

1. Control C **and** S reproduce the ATLAS C attempt-2 receipts (1e-6).
2. Treatment C reproduces the all-boom v1 receipts (1e-6).
3. The identity-capturing selection reproduces the canonical
   `_score_books` S exactly (1e-6).
Three frozen runs, one shared truth: any drift halts the grid.

## Endpoints

1. **Primary:** paired realized S (selected-book best actual), 53 slates,
   with the paired weekly-max co-primary block and the 240→187 selected
   threshold grid.
2. **Mechanism (anatomy A instrument):** each selected book's best
   overlap with the slate's tracked Milly winner versus the
   exposure-preserving chance null (`_book_overlap`, 500 reps, seed
   8163), per arm, on the 51 winner slates. A treatment that raises S
   without beating the chance null is volume, not aim — reported either
   way, gating nothing in this arm.
3. Descriptive: selected-book intersection between arms; paired C
   restated (must equal v1 by gate 2).

## Preregistered reading

- ΔS clearly positive with threshold-grid support at 194+: license a
  prospective shadow variant design (boom-deep generation) for the 2026
  fleet — production adoption ONLY through the prospective record.
- ΔS null while ΔC stands at +9: the selector cannot harvest boom depth;
  the next lever is selection-side (A7 ladder / A8 regret / S1 floor),
  and the reallocation is closed at this dose for the money path.
- ΔS negative: boom depth actively mis-feeds the coverage selector;
  closed permanently at this dose.

## Governance

Outcome-aware; one active historical-score arm at a time (nothing else
runs); create-only GCS receipts; reused Cloud Run job (rule 5); image
built clean-archive from the exact commit; runner/chain/protocol shas in
the launch manifest. No production change licensed by any outcome.

## Reality smoke (rule 1, outcome-blind — required before this freeze)

2023 W1, full mechanics: both arms generated (five seeds), reproduction
checks against the registered natives, budgets asserted equal per seed,
exact-80 selection for both arms, receipt serialized on the smoke path;
no actuals query issued, no score computed.

- Smoke disposition: **PASSED 2026-08-19, exit 0.** Runner output,
  verbatim:
  `{"cross_run_reproduction": null, "paired_delta_s": null, "run_id":
  "20260819-all-boom-selection-s-v1", "season": 2023, "seeds": 5,
  "selected_book_intersection": 26, "smoke": true, "week": 1}`
  — five seeds processed end to end; the in-path fail-closed gates
  (exact source reproduction per seed, equal candidate budgets, exact-80
  selection for BOTH arms) all held or the run would have raised; the
  two selected books share 26 of 80 lineups; the receipt serialized on
  the smoke path; no actuals query was issued
  (`cross_run_reproduction`/`paired_delta_s` null by design in smoke).
  With this record the protocol is FROZEN.
