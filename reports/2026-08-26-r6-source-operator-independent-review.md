# R6 matchup-source operator independent review

Date: 2026-08-26
Review disposition: **REJECT as a trusted execute boundary**
Severity summary: no P0; four P1 release blockers; three P2 robustness findings

## Review boundary and verified scope

This was an independent read-only static review of the corrected, untracked R6
matchup-source operator candidate:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py`
- `scripts/run_corpus_r6_matchup_source_operator_v1.py`
- `tests/test_corpus_r6_matchup_source_operator_v1.py`

Relevant existing contracts and current repository instructions were inspected
as needed, including `README.md`, `CLAUDE.md`, `HANDOFF.md`,
`src/nfl_dfs/research/corpus_r6_matchup_source_v1.py`,
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py`,
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py`, and
`src/nfl_dfs/research/corpus_v12_import.py`.

The independently verified candidate SHA-256 values are:

| Artifact | SHA-256 |
| --- | --- |
| Operator | `1cff827f90443ff97ac24c040f984a1f4f9f4be0ca0c65e10d8bc1f11df91ff5` |
| CLI | `085abe5b32d194bd57016cf72f304a2b212729d9b551a7eac4a17cca40bc14a5` |
| Focused tests | `135e09c930b2c3af30e552e4fd3f5b8e5c095514a789be9385bfa509b41d37f7` |

Before this report was added, targeted `git status` showed exactly those three
candidate files as untracked and showed no modification to the tracked
reference contracts or repository instruction files. Static compilation of all
three candidate files completed successfully without creating bytecode.

The author-reported focused pytest result is 27/27. That pytest invocation was
**not** rerun during this independent review. No pytest, cloud, BigQuery, GCS,
IAM, realized-outcome, scoring, promotion, or T230 action was performed. No
candidate file was edited, staged, or committed.

## Approval conclusion

The candidate is materially improved as a content-integrity and validate-only
operator, but it does not establish who is authorized to choose the content.
Exact reopening a caller-selected object proves only that the reopened bytes
match the supplied identity. It does not turn the object into an independent
authority root.

Accordingly:

- **P0:** none found.
- **Trusted execute:** **REJECT**.
- **Validate-only:** acceptable to retain if execute is hard-disabled until the
  frozen 54-entry authority catalog exists.

This follows the standing requirement in `HANDOFF.md:113-120`: execute must
remain source-blocked without the future frozen 54-entry authority catalog.

## P1 findings

### P1.1 — A caller can still mint a coherently rehashed mechanics-authority chain

The execute path accepts any capture-authority identity supplied by the same
caller and treats an exact reopen plus internal validation as authorization:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1229-1250`
- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1661-1694`
- `scripts/run_corpus_r6_matchup_source_operator_v1.py:53-64`
- `scripts/run_corpus_r6_matchup_source_operator_v1.py:192-223`

The public builder creates the carrier entirely from caller-provided bundle and
environment metadata and sets `capture_mechanics_authority=True`:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:898-955`
- public export at `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1747`

The future catalog is mentioned only in the module prose at
`src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:18-21`. There is
no frozen-catalog schema, pinned root identity, exact catalog read, or member
lookup in execute. The result then sets every exact-reopen flag and
`capture_mechanics_authority` from the fact that mode is execute, rather than
from rooted catalog membership:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1494-1500`

The focused fixture demonstrates the defect rather than disproving it. It
fabricates accepted/catalog-authority objects and code identities, calls the
public carrier builder, seeds the resulting identity, and successfully
executes:

- `tests/test_corpus_r6_matchup_source_operator_v1.py:48-170`
- `tests/test_corpus_r6_matchup_source_operator_v1.py:237-265`
- CLI equivalent at `tests/test_corpus_r6_matchup_source_operator_v1.py:684-719`

The substitution tests at
`tests/test_corpus_r6_matchup_source_operator_v1.py:338-449` alter a bundle or
carrier while retaining the old expected identity. They correctly prove that
one-sided byte drift cannot cross an existing content identity. They do not
test the controlling attack: construct alternate accepted, catalog-authority,
catalog, bundle, and carrier objects; give every object a matching new exact
identity; and pass the new carrier identity to execute. That chain currently
passes and receives mechanics authority.

Removing or hiding `build_capture_authority_v1` would not repair this issue;
the same canonical JSON can be constructed independently. Execute needs a
non-caller-selectable trust root.

### P1.2 — Accepted-v12, catalog-source, and ordinal authority are not semantically linked

The accepted-v12 identity is normalized and copied into the bundle at
`src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:680-683`, then
its object is exact-read during execute at
`src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1272-1283`.
Those bytes are discarded. The operator does not canonical-parse the object,
validate an accepted-v12 schema or receipt hash, reconstruct the accepted
member, or derive task and player-catalog authority from it.

The player catalog itself has useful schema/task/self-hash checks at
`src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:627-650`, but its
nested source-authority object is only treated as an object identity. It is
exact-read and discarded without a positive receipt schema or a link back to
the accepted-v12 member:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1300-1314`

Task ordinals are only caller values bounded to 0 through 53 and compared
between the caller bundle and caller carrier:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:477-494`
- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1269-1270`

The test fixture's accepted object and catalog-source-authority object use
unrelated arbitrary fixture schemas and nevertheless authorize execution:

- `tests/test_corpus_r6_matchup_source_operator_v1.py:74-107`
- `tests/test_corpus_r6_matchup_source_operator_v1.py:237-265`

The repository already contains the required semantic pattern. The accepted
slate can be exact-reconstructed with
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py:504-524`; the
accepted task/ordinal and complete `{id,pos,team,opp,game_id,salary}` player
projection are derived at
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py:97-172`; and the
exact matchup catalog is compared to that projection at
`src/nfl_dfs/research/corpus_r6_v2_one_slate_execution_v2.py:307-359`.

### P1.3 — Declared code identity is not tied to the code that executes

`build_code_identity_v1` accepts arbitrary commit, path, hash, and size claims.
`validate_code_identity_v1` validates their schema, formatting, role order, and
self-hash but never reads or hashes an actual artifact:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:497-590`

Execute compares only the same transported mapping in the bundle and carrier:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1335-1339`

The security-relevant CLI is absent from `_CODE_ARTIFACT_ROLES`:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:74-79`

The tests use nonexistent role-derived paths, fabricated hashes and sizes, and
a fabricated repository commit, and the resulting identity authorizes execute:

- `tests/test_corpus_r6_matchup_source_operator_v1.py:48-67`

Consequently, accidental operator, CLI, semantic-contract, family-producer, or
extract-producer drift is not detected. A transported declaration can continue
to describe old bytes while different bytes execute.

### P1.4 — Query and relation provenance is a coherent assertion, not independently rooted evidence

The registered relation set is derived from relation metadata and extracts
embedded in the same input bundle:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:804-889`

The query-job identity is only the canonical hash of the embedded `query_job`
mapping:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:892-895`

Execute compares those claims to copies in the caller-selected carrier:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1316-1354`

The semantic source contract rigorously checks internal relation/extract
coherence, including schema, exact-extract hash, and row count, at
`src/nfl_dfs/research/corpus_r6_matchup_source_v1.py:2292-2376`. It does not
make the embedded BigQuery job ID or relation etag externally authoritative.

This operator correctly avoids a live BigQuery call. To remain offline and
outcome-blind, it should instead exact-read a positively validated immutable
source-producer receipt, or require the independently rooted frozen catalog to
bind equivalent producer evidence. A coherent replacement of query, relation,
extract, bundle, and caller-selected carrier currently passes.

## Minimal safe correction

### Immediate correction before the future catalog exists

Keep the useful validate-only path unchanged and make execute fail
unconditionally with a specific error such as `frozen 54-entry R6 source
authority catalog unavailable`. Prefer blocking before any cloud-client
construction. Merely requiring another CLI path, catalog identity, SHA, or
self-hashed object supplied by the same caller does not add authority.

Validate-only should continue to:

- parse the bounded canonical bundle;
- run the full semantic capture replay in memory;
- construct no GCS/BigQuery client;
- publish nothing externally; and
- report `capture_mechanics_authority=false` and every unrelated authority
  field false.

### Minimum future catalog trust root

The future execute boundary requires one independently reviewed canonical
`corpus-r6-matchup-source-authority-catalog/v1`-style artifact with these
properties:

1. Its exact `{uri,generation,sha256,bytes}` identity is pinned by a trusted
   release/deployment boundary or verified signature. It is not selected solely
   by the CLI caller, and an alternate coherently self-hashed catalog is not
   accepted.
2. Execute exact-reopens that pinned root before any publication and validates
   an exact positive schema, self-hash, explicit outcome blindness, and explicit
   false values for every authority outside matchup-source capture mechanics.
3. It contains exactly 54 ordered, unique members with complete coverage and no
   duplicate or ambiguous task IDs, task ordinals, source ordinals, or carrier
   identities.
4. A root-level accepted panel identity plus each member's accepted membership,
   task-acceptance identity, and accepted v12 carrier identity supply the exact
   inputs needed for `reconstruct_one_accepted_v12_slate(...,
   require_authoritative=True)`.
5. Each member binds its canonical derived season/week/slate/task and ordinals
   and exactly one capture-authority identity. Execute derives the permitted
   carrier identity from that member. A caller-provided carrier identity may at
   most be an equality cross-check; it cannot be the root selector.
6. The selected capture carrier continues to bind the exact input bundle,
   player catalog, catalog-source authority, registered source set, query job,
   family definitions, code/build identity, project, bucket, and output prefix.
7. The catalog-source authority is a positively validated receipt binding the
   accepted reconstruction/member and the complete accepted player structural
   projection. The exact player catalog must equal that derived projection.
8. Query/relation/extract provenance is bound either directly by the trusted
   catalog generator or through an exact immutable source-producer receipt with
   a positive schema covering query-job hash, rendered-SQL hash, complete
   relation/schema/etag/extract/count set, input-bundle identity, and producer
   code/build identity.
9. Actual critical runtime artifacts or a trusted immutable image/build digest
   are compared to the frozen code identity. The critical set includes the
   operator, semantic source contract, CLI, family-definition producer, and
   source-extract producer. Follow `CLAUDE.md:54-57` for an explicit repair-SHA
   override and avoid a circular self-pin.
10. The operator result records the frozen catalog identity and selected member
    digest/ordinal. `capture_mechanics_authority=true` is emitted only after all
    root, member, reconstruction, catalog, source-producer, environment, and
    code checks pass.

The minimal catalog member can remain small: accepted-chain inputs, canonical
task binding, and exact capture-carrier identity are enough if the selected
carrier and its subordinate positive receipts carry and validate all lower
identities. The essential property is that the catalog root and member are not
mintable or replaceable by the same caller asking execute to trust them.

## P2 findings

### P2.1 — Huge JSON integers can escape the controlled error boundary

`_canonical_object` catches Unicode, JSON-decode, recursion, and source errors
but not the `ValueError` raised by Python's bounded integer conversion for an
overlong JSON integer:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:275-290`

Use a bounded `parse_int` policy and/or catch `ValueError`, then convert it to
`CorpusR6MatchupSourceOperatorV1Error`.

### P2.2 — An unhashable result mode raises raw `TypeError`

The result validator performs set membership before checking that `mode` is a
string:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1514-1518`

A JSON array or object in `mode` raises raw `TypeError`. Type-check first so all
malformed receipts fail through the controlled contract exception.

### P2.3 — GCS size is enforced after the full object is allocated

The GCS reader reloads the pinned generation and then calls
`download_as_bytes` before comparing bytes and hash:

- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1143-1163`

An exact generation whose real size exceeds the identity's claimed bounded size
can allocate the complete object before rejection. Compare the reloaded blob's
size to the expected byte count before download, or perform a bounded read of at
most `expected_bytes + 1`.

## Controls that passed static review

These controls are useful and should be retained:

- strict canonical input schema, byte ceiling, self-hash, tree/row ceilings,
  explicit outcome blindness, and explicit false-authority policy at
  `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:653-716`;
- positive exact carrier/result field sets and rejection of unknown fields;
- honest validate-only authority and publication flags at
  `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1603-1615` and
  validate-only isolation at `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1673-1683`;
- CLI mutually exclusive explicit modes, validate-only cloud isolation, and
  bounded no-follow stable descriptor reads at
  `scripts/run_corpus_r6_matchup_source_operator_v1.py:34-65` and
  `scripts/run_corpus_r6_matchup_source_operator_v1.py:68-180`;
- memory-store create-once/exact-read behavior at
  `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1092-1132`;
- GCS `if_generation_match=0`, generation-pinned reload/download, returned
  generation validation, byte/hash binding, and immediate exact reopen at
  `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1135-1194`;
- preflight semantic capture before external writes at
  `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v1.py:1695-1699`.

These establish strong canonicality, drift detection against an already fixed
identity, create-once publication, and fail-closed local transport. They do not
replace an independent authorization root.

## Missing adversarial coverage

Before trusted execute can be approved, focused tests should include:

1. A full coherent alternate chain: new accepted object, catalog-source
   authority, player catalog, query/relation/extract set, bundle, carrier, and
   matching exact identities. It must fail because its carrier is not the
   selected member of the pinned catalog.
2. A syntactically valid, self-hashed 54-entry alternate catalog supplied by the
   caller. It must fail because its root identity is not trusted.
3. Pinned catalog wrong URI, generation, hash, or byte count, plus missing,
   extra, duplicate, reordered, or ambiguous members.
4. Accepted-v12 wrong schema, task, task ordinal, source ordinal, acceptance,
   carrier, or player projection despite a coherent caller carrier.
5. Catalog-source authority with a valid exact identity but wrong schema or no
   link to the accepted member/player projection.
6. Actual code-file or trusted-image drift while transported code metadata is
   unchanged; also coherent replacement of both code metadata and caller
   carrier. Include CLI drift.
7. Coherent query job, relation etag/schema, and extract replacement, including
   an alternate producer receipt not present in the pinned catalog member.
8. Generation-pinned GCS object with correct generation but wrong hash, wrong
   returned generation, and actual size larger than claimed before download.
9. Local bundle and authority-identity symlink, hard-link, and in-read metadata
   drift cases; the existing symlink and metadata-drift coverage should remain.
10. Huge-integer canonical JSON and unhashable result-mode inputs, requiring
    controlled contract errors rather than raw exceptions.

## Final recommendation

Do not commit or describe the current execute mode as authoritative. Either
remove/hard-disable execute in this candidate and retain validate-only, or add
the independently pinned 54-entry catalog root and all selected-member,
accepted-chain, source-producer, and actual-code checks above before requesting
another trusted-execute review.
