# ATLAS minimal C test — local smoke failure disposition (frozen record)

**Date:** 2026-08-18 evening
**Rule applied:** "a reproduction failure there is a halt-and-disposition,
not a retry" (recorded next action, 2026-08-18 13:20 state). The smoke was
halted, classified read-only, and dispositioned here before any rerun.

## Failure

The first local outcome-blind smoke (2023 W1, `--smoke`) failed closed at
`_slate_frame`: `ATLAS C artifact rows include DST players`.

## Classification (read-only evidence)

The frozen runner assumed the pinned money-world artifacts store
skill-only rows and reconstructed DST from the snapshot with
`draw_idx=-1`. Direct inspection of the pinned 2023 W1 R0 artifact
(`cand_scores/20260815-atlas-money-worlds-r0-v1/2023_w1_886e19454d2e.npz`)
shows the artifacts store the **complete generation slate**: 773 rows =
756 skill + 17 `DST_*` rows, the DST rows carrying exactly the constant
projection broadcast (zero draw variance) that production's `draw_idx=-1`
path emits. This matches the artifact writer's contract
(`engine._score_artifact_payload` persists every slate row). The defect is
in the frozen runner's schema assumption, not in the artifacts, the
census, or the lever; the support census verified snapshot/candidate
counts and never asserted artifact row composition.

## Disposition: amend, revalidate, then rerun once

Consumer-side amendment to `_slate_frame` and one `run()` assertion,
freeze doc re-pinned (amendment section + new SHA-256 in the runner):

1. All artifact rows form the slate in artifact order with
   `draw_idx = 0..n-1` (DST included, consuming its stored constant
   rows — byte-identical world matrices to the source panel's
   `draw_idx=-1` broadcast).
2. Strictly stronger fail-closed checks: duplicate artifact ids fail;
   ANY snapshot row absent from the artifact fails (the old contract
   tolerated non-DST-only leftovers); an artifact with no DST rows
   fails; DST artifact rows with nonzero draw variance fail (the
   constant-DST law made explicit).
3. Faithfulness is not asserted by construction: the runner's exact
   native-reproduction gate (registered natives vs regenerated, plus
   artifact-totals and actual-parity gates) remains the arbiter, exactly
   as frozen.

Contract tests updated to the real schema (16 pass, including three new
fail-closed cases). The single sanctioned smoke rerun under the amended
freeze is this disposition's validation step — not a silent retry — and
its result is recorded in HANDOFF.md.

Two prior cloud smoke failures (`atlas-minimal-c-smoke-d5hh7`, `-6vnwt`,
exit 2, image allowlist) are unrelated infrastructure failures already
repaired at `18b3234`; the redundant in-flight image build at `9dfa7ae`
was cancelled (it would have baked the defective runner), and the C-test
image rebuilds from the amendment commit.

## Addendum: second smoke failure and Amendment 2 (same evening)

The amended smoke progressed past the corrected slate reconstruction and
failed closed at the next frozen gap:
`role_draws treatment requires alternate belief slate/draws`
(engine.py, production role family). The acquisition environment carries
`N_EPISTEMIC=12` / `EPISTEMIC_FAMILY=role_draws`, whose belief inputs
come from the role registry pipeline at generation time and are not
reconstructible from the pinned artifacts or snapshots.

Disposition: the role family is arm-invariant by code — its generation
never reads the boom world ranking — so faithful arm comparison does not
require regenerating it. Amendment 2 (freeze doc re-pinned at
`966c4c7f…`): both arms generate with the role dose at zero and receive
the SAME registered role natives spliced verbatim at their registered
cand_ix positions; injected rows carry the artifact's own world totals
(pinned inputs, like the draws); registered-order player lists keep
downstream recomputation bit-consistent; collisions, budget mismatches,
missing players/natives fail closed; the acquisition-record environment
validation still checks the faithful environment; the exact
native-reproduction gate is unchanged, its evidential force now resting
on every regenerated row — precisely the population the lever can move.
One residual fidelity caveat is disclosed rather than hidden: in the
source run the role rosters sat in the dedup universe for the families
generated after them; regeneration reruns those families with the role
rosters absent from `seen`. Any resulting divergence is caught
row-exactly by the reproduction gate (fail closed, halt-and-disposition),
so a passing gate PROVES the caveat did not bind on that cell.
Contract tests: 17 pass, including the new splice/collision/budget
fail-closed cases. Third sanctioned smoke recorded in HANDOFF.md.

## Addendum 2: third smoke failure and Amendment 3 (same evening)

Smoke #3 cleared reconstruction and role injection and failed closed at
the splice budget: natives 255 versus regenerated 164 + injected 12 —
exactly the 80 missing lev candidates of a 40-entry generation basis.
The source panels were true-80 replays (basis 80 → 160 lev; the coherent
support census records exactly 160 leverage candidates per cell); the
frozen runner passed `N_ENTRIES=40`. Amendment 3 corrects the basis to
80 (freeze doc re-pinned). Same defect class as Amendments 1-2: frozen
without a single reality contact; each gap was caught by a fail-closed
gate exactly as designed. Fourth sanctioned smoke recorded in HANDOFF.md.
