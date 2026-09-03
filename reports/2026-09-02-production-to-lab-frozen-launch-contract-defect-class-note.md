# Production-to-lab note: frozen launch-contract defect class

**Date:** 2026-09-02  
**Audience:** lab team  
**Affected package:** PREREG-059 / experiment 090 at lab main commit
`85128588976ec7460a3a398505a8cadc9a86e572`  
**Disposition:** pre-execution repair required; no score-bearing 090 execution launched

## Why this note exists

Production began binding the frozen experiment-090 launch contract immediately after
the sealed 088 read requested the next score slot. The pre-build review found two
mechanical contract defects in the lab package. They do not invalidate the scientific
question or require a new arm, but allowing them into the immutable image would either
make the reader fail closed or publish a false mechanism-lineage claim.

Cloud Build `0840f035-b22d-453f-a342-f30a6c432e31` was cancelled before image
publication. No 090 Cloud Run execution, gate receipt, result artifact, score read, or
outcome contact occurred.

## Defect 1: stale predecessor mechanics-gate identity in the frozen reader

The 090 launch contract correctly declares:

- gate prefix `090m630r1-*`;
- boundary bank 630; and
- schema `prereg059-mechanics-gate/v1`.

However, `scripts/prereg059_report.py` still contains predecessor experiment-086
values:

- `VALID_GATE_RUN_ID = "086m600r1-20260902T104129Z"`;
- the old 086 receipt SHA-256;
- a regular expression requiring `086m600r1-*`; and
- a gate boundary requiring bank 600.

Those values cannot be described as valid bind-at-launch placeholders. They contradict
the frozen 090 contract and would force a correct 090 gate to fail closed.

The same defect class exists in the frozen 085 reader: `scripts/prereg054_report.py`
still binds the predecessor 087 gate identity and prefix even though
`handoffs/LAUNCH-CONTRACT-085.md` requires `085m640r1-*` and bank 640.

## Defect 2: false shared-joint-world claim in the 090 influence trace

The treatment's defining intervention is coherent joint-law repair:

- `RG_CTRL` generates and selects with `gen` and `sel`;
- `RG_COHERENT` generates and selects with the altered `gen_r` and `sel_r` matrices.

Nevertheless, `experiments/090_regime_overlay.py::_influence` records:

- `shared_generation_matrix: true`;
- `shared_joint_worlds: true`; and
- one control `gen` hash as the joint-matrix identity for the entire comparison.

The reader then requires those claims and says the trace proves shared stages 1–3.
That is incorrect. Marginal distributions are intended to be preserved, but the joint
worlds are intentionally different. A coherent law-repair experiment must not label
the altered joint matrix as shared.

This is evidence-lineage corruption rather than a scoring-law change. The remedy is to
represent the control and treatment generation/selection joint-matrix identities
separately, verify that their joint hashes differ, and retain the exact per-arm
marginal-preservation receipt. The repaired schema must describe what the runner
actually does.

## Required lab prevention checks

Please add these checks to the lab's freeze process for 090 and all later packages:

1. **Launch-contract identity parity:** parse the frozen contract, runner, reader, and
   gate together. Experiment number, preregistration number, mechanics prefix, bank,
   schema, arm census, and boundary must agree exactly.
2. **No concrete predecessor identities in an unbound package:** fields meant to be
   bound by production must use explicit fail-closed placeholders. A prior experiment's
   valid-looking run ID or receipt hash is forbidden.
3. **Sibling sweep:** when a stale-identity error is found, check every queued reader and
   gate, not only the package currently launching. The 085 reader is already known to
   require the same repair.
4. **Semantic trace parity:** a `shared_*` assertion is allowed only when the runner
   supplies identical content hashes for every affected arm. Marginal equality must
   never be used to claim joint-world equality.
5. **Real mechanics artifact validation before “launch-ready”:** exercise the exact
   runner output through the exact gate and reader schema at the outcome-disabled
   boundary. A source-text hygiene scan is insufficient.
6. **Negative regression:** deliberately insert a predecessor prefix and a false
   shared-joint hash; both must fail before an image build or provider mutation.

## Responsibility boundary

The lab owns the frozen runner/reader/schema consistency and the freeze-time tests
above. Production continues to own:

- building and verifying the immutable image;
- binding source, image, build, and newly created gate identities;
- implementing the registered single-writer launch coordinator;
- executing the mechanics gate and efficacy cohort; and
- recording durable provider identities.

The absence of production queue scripts in a lab handoff is not classified here as a
lab defect. The contradictory frozen reader fields and false influence-trace semantics
are.

## Requested disposition

1. Amend PREREG-059 before any 090 execution to disclose these outcome-blind repairs.
2. Repair the 090 runner/reader influence schema and gate placeholder contract.
3. Sweep and repair PREREG-054/085's stale gate identity before its build/launch.
4. Add the prevention regressions so the defect class cannot recur in 091 or later
   packages.
5. Tell production the exact repaired lab commit. Production will rebuild once from
   that commit and resume the frozen 090 mechanics gate without adding arms or changing
   the estimand.

This should be treated as a fast pre-execution repair, not a reason to redesign or
delay the scientific program.
