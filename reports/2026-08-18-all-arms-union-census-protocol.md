# All-arms union candidate census — protocol (B1, DRAFT for operator freeze)

**Protocol ID:** `20260818-all-arms-union-census-v1`
**Status:** DRAFT — outcome-facing, so execution requires the operator to
pin this document's SHA-256 first; the runner refuses to execute without
`--protocol-frozen`.
**Class:** descriptive ceiling measurement; diagnostic-only; adopts,
promotes, and closes nothing.

## Question

What is the mean-C ceiling of "selection from the corpus" in its widest
defensible sense — the best legal candidate per slate across EVERY panel
ever registered (104 panel_run_ids in `replay_candidates_staging`, per
the 2026-08-18 discordant-pair feasibility census)? Anchors: today's
selected book 176.06 mean, canonical pool C 181.07, CBWU-OI pool C
186.73, operator target ≈ 194. This single number decides how much of
the offseason belongs to selection/admission versus construction/law
work — before any union-admission policy is designed.

## Frozen mechanics (implemented, offline-tested)

`research/all_arms_union.py` + `scripts/union_candidate_census.py`:

1. **Mechanical inclusion.** The candidate extract takes ALL panels for
   the 54-slate 2023–25 corpus, with no arm filtering — that bound on
   the selection effect is what keeps the ceiling readable. The extract
   query text and its row counts are recorded in the run receipt.
2. **Legality revalidation.** Every distinct roster is re-audited under
   the CORRECTED slate snapshot and the production strategy contract
   (QB+2, one bring-back, $49k floor, RB rules) via the frozen forensic
   `audit_roster`; illegal and unmatched rosters are dropped AND counted.
3. **Revaluation.** Every roster is scored from corrected snapshot
   actuals; stored cross-era labels are reconciled (mismatches counted)
   but never trusted.
4. **Report.** Per-slate union C with panel attribution of the argmax
   roster, aggregate mean/median, the full 240→187 union grid, by-season
   splits, and union-minus-anchor deltas. Create-only JSON with SHA-256.

## Interpretation rules (frozen before any number)

- Union C is a slightly OPTIMISTIC ceiling: the arms were outcome-viewed
  at panel level. Per-arm attribution is reported so concentration in
  one rejected arm is visible; heavy attribution to a single
  falsified-law arm discounts the ceiling accordingly.
- Decision reading, stated in advance: union mean C ≥ ~192 makes the
  union-admission policy (B2 — CBWU-OI's complete-union admission
  generalized across arms, unchanged selector) the next design-lane
  priority, evaluated one-shot/LOSO under the operator's frozen utility
  and the standing amendment requirement; union mean C ≲ ~188 says even
  everything ever generated caps well short of 194, and the target is
  construction/law-bound — a result that redirects, not disappoints.
- Cross-era roster identities transfer; their generating beliefs do not.
  No claim about any arm's validity is made or reversed.

## Cost and lane

Two BigQuery extracts plus a deterministic local/cloud aggregation over
retained files; no simulation, no heavy slot.
