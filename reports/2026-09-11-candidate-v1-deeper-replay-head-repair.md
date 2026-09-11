# Candidate-v1 deeper historical-HEAD replay diagnosis and repair

Date: 2026-09-11

Status: implementation committed and pushed for independent review; no
freezer, capture, warehouse, storage-write, Cloud Build, or Cloud Run action
was performed by this repair.

## Trigger and bounded diagnosis

The capture-plan freeze at clean pushed Commit A
`e9cacf6b56a3f23bfd6ba3ee4b75c8962cdaee64` passed the repaired outer
candidate binding, then failed safely before a lock existed:

```text
candidate-authority v2 exact reopen failed: candidate-authority v2
predecessor replay failed: fixed-G0 candidate release/receipts differ from
exact predecessor replay
```

Attempt 3 exited 2, wrote no stdout, and created no capture-plan lock. The
sealed seven-pack-v4 terminal remains generation `1789106359079526`, SHA-256
`1de61029e63907530d1d4182c1b37189828be4a9d9e635bd61fe2529b8af34e5`.
It must not be recaptured or relabelled.

The fixed-G0 candidate root binds its original clean publication HEAD
`346b2a27a55c29cd5c2a30719b1a0739baae4b50`. Candidate-v1 derives two
otherwise non-scientific representation leaves from `git_head(...)` at replay
time:

1. `panel_derivation_receipt.g0_source_commit_sha`, emitted by the tracked G0
   authority-lock replay.
2. `catalog_terminal_final_lock_binding.git_commit_sha`, emitted by the
   catalog terminal-authority replay and copied into all 54 slate receipts and
   the panel receipt.

Fifty-six generation-exact, outcome-blind reads of the retained candidate root,
panel receipt, and 54 slate receipts confirmed that all 56 direct leaves retain
`346b2a27...`; the panel is 86,053 canonical bytes and the first receipt is
27,899 bytes. No 230-MB full candidate replay was needed for diagnosis.

An exact recursive comparison against the deterministic Commit-A projection
found precisely 168 changed scalar paths:

- 56 direct HEAD leaves: 54 slate catalog bindings, one panel catalog binding,
  and one panel G0 source commit;
- 54 slate-receipt self-hashes;
- 54 panel-row slate-receipt hashes;
- two copies of the slate-receipt manifest hash;
- one panel self-hash; and
- one candidate-bundle self-hash.

There was no other body-field, ordering, authority, source, candidate, or
scientific-output delta. Diagnostic retained/projected hashes at Commit A were:

- receipt manifest:
  `56c367efa2c009244ed55f78ff9b4832bd8625f88439bd1848c914cda9d1bf79`
  to
  `5077149df03ad3799adadb684abe8ce234b34cf4f2d879ea1f3ab814e798de43`;
- panel self-hash:
  `9913209beba317a1b6f160bd910a532ce54da528f19951405f1039b4b404211d`
  to
  `56c36e2169417e5d322397b8c35dfb2790c7480898b4b7eb40a050ff8d53a96a`.

## Fail-closed repair

Pushed implementation commit
`025d8ca8e9c8b8b9520fc166f86342c4d731ac40` on branch
`codex/seven-pack-v4-predecessor-diagnosis-20260911` changes only the existing
descendant reopener and its test module. Frozen candidate-v1/v2/release code is
unchanged.

The descendant reopener now:

- validates retained bundle, panel, and all 54 receipt self-hashes, schemas,
  cardinalities, ordinals, manifests, and a single exact terminal-lock binding;
- requires the 56 retained direct HEAD leaves unanimously equal the outer
  candidate implementation commit;
- permits only their projection to the real durable clean current HEAD and
  deterministically recomputes exactly the 112 dependent hashes;
- requires exact historical-commit, current-commit, and runtime-byte equality
  for the pinned 19 transitive authority-validator modules and nine tracked
  lock/evidence selections; the exact path surfaces are public constants and
  test-pinned;
- validates the projected bundle with the unchanged ordinary v1 validator and
  the real current `git_head` callback;
- separately validates the retained bundle with the unchanged ordinary v1
  validator and a repository-root-bound historical `git_head` callback;
- gives each validation a fresh outer-authority manifest-gated reader and its
  own completion check, so neither replay can borrow the other's read census;
- derives both catalog receipt inputs only from the already opened outer
  authority, never from a caller- or panel-selected identity;
- rebuilds and returns only the retained historical v2 bundle and exact root;
  the current projection is validation-only; and
- rechecks the actual clean current HEAD at the end to close replay-time
  worktree/HEAD changes.

Any code, lock, evidence, schema, cardinality, order, stable binding, callback
root, manifest read census, or final HEAD drift fails closed. The repair grants
no publication, capture, scoring, realized-outcome, graph, promotion, or policy
capability.

## Validation

All tests were run serially from the isolated worktree with bytecode/cache
output disabled:

- descendant reopener: 23 passed in 37.36 s;
- capture-plan-v3 integration: 9 passed in 6.48 s;
- unchanged frozen candidate-v1 regression: 36 passed in 160.57 s;
- Python compilation and `git diff --check`: pass;
- real Git blob audit: all 19 implementation and nine selection paths are
  byte-identical at historical HEAD `346b2a27...` and Commit A `e9cacf6b...`.

The focused suite includes the exact 168-path regression and refusals for
coherently rehashed stable-lock drift, receipt/panel schema-cardinality-order
drift, historical-only lock drift, descendant dependency drift, dirty guarded
paths, and a callback-root substitution. It also pins the
two-reader/two-completion call contract and final-HEAD TOCTOU refusal.

## Integration order

1. Obtain an independent immutable-diff and focused-test GO for `025d8ca8`.
2. Integrate only this repair onto the current production Commit-A line, add
   the reviewed HANDOFF, and push a clean new Commit A to `origin/main`.
3. From that exact durable commit, retry `freeze-capture-plan` once against the
   already sealed v4 generation `1789106359079526`.
4. Validate its sole create-once lock/receipt, then commit and push that lock as
   distinct Commit B.
5. Only after Commit B may the separately reviewed source-v3 and discovery
   successor chains be integrated. Their cloud launch remains forbidden here.
