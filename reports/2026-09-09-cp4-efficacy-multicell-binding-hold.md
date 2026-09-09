# CP-4 efficacy multicell binding review — HOLD before provider implementation

Date: 2026-09-09  
Production disposition: **HOLD the 162-cell CP-4 efficacy build/launch path.**  
Scope: score-free generation transport only. The accepted CP-4 allocation law,
candidate budgets, selectors, judges, K80 memberships, outcomes, and scoring
were not changed or opened.

## Result

The audited-membership repair at lab commit
`f18e46870e9940afb42e79f271ca4a3847ce1ce8` is still the right narrow repair
for the receipt-mapping defect. However, the efficacy branch cannot yet execute
the 162-cell cohort declared by its own contract. Its reused composed producer
is physically bound to one mechanics cell: `2023-w18-b740`.

Production discovered this while preparing the missing provider launcher. The
launcher work was discarded before build or cloud action. Both Cloud Run lanes
remain idle, no CP-4 namespace was claimed, and no outcome or score was read.

## Exact conflict

The efficacy contract and module declare:

- seasons 2022–2024;
- weeks 1–18;
- banks 740–742;
- 54 cells per bank and 162 receipts total.

But the path `cp4_efficacy_cohort.composed_cell_receipt()` calls
`cp4_d800_mechanics.composed_cell(season, week, bank, ...)`, whose preflight
does all of the following through the singleton `nfl2.ctxcore.binding` module:

1. `binding.CELL` is the literal `2023-w18-b740`.
2. `binding.SIDECAR_PATH` is the single tracked file
   `results/cp4_frame_binding_2023-w18-b740.json`.
3. `binding.CP4_FRAME_BINDING` fixes season 2023, week 18, and bank 740.
4. `preflight_boundary()` requests private facts with
   `cell_facts(..., binding.CELL)`, not the requested efficacy cell.
5. `load_bound_cp4_sidecar()` loads that same singleton sidecar.
6. `bound_snapshot()` compares every requested frame and generation draw
   against the singleton sidecar's frame/draw identities.
7. `cp4_gate()` authenticates the supported cell using `binding.CELL`, again
   not the requested cell.
8. The container image-mode record attests that one sidecar's bytes and hash.

Only one declared efficacy cell is the bound cell. The other **161 of 162**
cannot honestly satisfy the current binding. Merely scheduling 162 Cloud Run
tasks would either fail those cells or, after an unsafe relaxation, stamp the
wrong slate's pre-lock authority onto them.

There is a second container-only blocker: the score-free cohort receipt asks
for `mechanics._git("rev-parse", "HEAD")` when the composed gate carries no
`source` member. The accepted CP-4 image deliberately has no `.git` directory.
The immutable packaging/source identity must therefore arrive through the
frozen execution plan and be checked against the baked image-mode attestation;
it cannot be rediscovered from Git in the container.

## Required narrow successor

Please preserve `f18e468` and return one independently reviewable, score-free
multicell binding successor with these properties:

1. Replace the singleton execution dependency with an explicit per-cell
   binding selected by the requested `(season, week, bank)`. Do not mutate a
   module global between tasks.
2. Freeze a closed 162-cell binding-root manifest. Every cell must name the
   exact sidecar/pre-lock authority identities it consumes; unsupported cells
   must be typed unavailable before generation and may not silently disappear.
3. Parameterize the composed path end to end. Private-fact selection, sidecar
   load, frame/draw checks, gate authority, seed law, and receipt cell must all
   use the same explicit requested cell.
4. Make image mode attest the multicell binding root by content plus the exact
   packaging commit. Retain the host rule for ordinary worktree execution.
5. Carry the immutable packaging/source commit explicitly into the Git-free
   container receipt and verify it against the baked attestation. Remove the
   container dependency on `git rev-parse` without weakening the host check.
6. Add adversarial tests proving that a 2022 cell cannot consume the 2023-W18
   sidecar, bank 741 cannot consume bank 740's binding, a missing/duplicate
   manifest member refuses, and a mismatched packaging identity refuses.
7. Run one outcome-disabled boundary smoke on a non-`2023-w18-b740` cell—use
   the earliest supported/smallest edge cell available—before any full cohort
   build or launch. It must reach binding selection and the composed path, not
   merely parse the manifest.
8. Only after that smoke and independent review should production add the
   registered three-bank provider launcher and create-once 162-cell seal.

The provider implementation should remain simple once this source boundary is
real: one 54-task execution per bank, banks serial, parallelism 18, 2 vCPU / 8
GiB per task unless the reviewed resource contract says otherwise, zero
retries, exact all-generation namespace census, and a terminal seal only after
162 exact receipt identities validate. No scoring or outcome access belongs in
that launcher.

## Queue effect

This is a **CP-4-only hold**, not a queue-wide hold. PREREG-076 R2 remains the
next scoring priority and is independently awaiting review of production
candidate `72ce2543bdb76b0489b2d695385ab425382a7f18`. Week-1 capture work also
remains independent.
