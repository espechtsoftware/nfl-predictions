# Pre-lock lineage review repairs: selective production port

**Date:** 2026-09-02

**Branch:** `codex/prelock-lineage-review-repair`

**Review commit:** `9ee67dc7deab893b52dc6d4f0579666ad8b97947`

**Integrated production base:** `origin/main`
`cf0ab928` (the executable base remains `8728642e`; intervening production
commits update only `HANDOFF.md`)

**Implementation commits:** `bd006ada`, source-checkout hardening `7186e878`,
runtime image/source binding `958a5444`, and independent adversarial repair
`0c65a3cc`

## Result

Every code-level concern in
`2026-09-02-prelock-lineage-phase1-production-review.md` is now either repaired
in the inactive selective port or enforced as an explicit false-authority gate.
The donor branch was not merged. The current immutable v1 candidate-lineage
contract, typed selector events, hardened graph-v2 projection, and source-set
v6 scoring files remain unchanged.

Production advanced from the tested code base `40aaba98` to `8728642e` while
this repair was closing. That one-commit delta changed only `HANDOFF.md`; it is
merged here so the current experiment-087 operational record is preserved.

The implementation is still **default-off**. It has no CLI, route, scheduler,
deployment, graph loader, or automatic settlement caller. No cloud object,
BigQuery row, Neo4j row, model, score, lineup policy, paid entry, or deployment
was changed by this work.

The first claimed-complete branch tip, `69488cc2`, was **not accepted on test
counts alone**. A second independent adversarial review reproduced two further
P0 defects and three P1 defects: cross-root rescue joins, changed-code partial
resume, multi-statement BigQuery writes, exact-lock timestamp acceptance, and
self-attested provider execution identity. Commit `0c65a3cc` repairs or
explicitly downgrades all five without changing scoring or graph behavior.

## P0 disposition

1. **Immutable v1 collisions — repaired.** New detailed evidence uses
   `prelock-lineage-capture-envelope/v2`; the published sidecar is constructed
   through the unchanged `prelock_candidate_lineage_v1` builder and validator.
   No second graph-v1 packet was added. The existing graph-v2 adapter is reused.
2. **Five-seed incompatibility — repaired.** R0-R4 are normalized into one
   v1-linear `native-union` stage followed by one fixed-budget CBWU stage. The
   integration test uses real `CandidateBatch` objects, generation ledgers,
   `combine_cbwu_books`, typed `CoverageSelectorEvent` replay, and the immutable
   v1 seal. Requests, attempts, occurrences, cross-seed dedupe, pool-cap loss,
   CBWU admission, selector decisions, and final-book rows reconcile.
3. **Subsecond provider ordering — repaired.** Exact provider creation times
   retain microseconds. The whole-second graph contract receives a conservative
   ceiling of the sidecar provider time, so it can never claim to predate the
   provider object. The `.500000Z` same-second case is tested.
4. **Later-clock retry — repaired.** The first create-once capture contains the
   exact compressed selector matrix and everything needed to rebuild the v1
   sidecar and graph projection. Retries reopen before generation, resume from
   every publication boundary, and never reread salary or regenerate lineups.
   Before any incomplete retry writes, it regenerates and exact-compares the
   adapter and policy manifests, revalidates the current source binding, and
   compares the current solver/process receipt with the capture. A changed
   source mode or image receipt fails before another object is attempted. A
   complete root is read-only even after lock.
5. **Missing durable root — repaired.** The write set is exactly five objects:
   capture authority, raw matrix, immutable v1 sidecar, graph-v2 projection,
   and a fifth/root-last final manifest. The final manifest binds all four
   predecessors by role, fixed name, URI, generation, SHA-256, byte count, and
   trusted provider creation time. Every predecessor and the root are exact-
   reopened before completion. The former donor terminal is intentionally not
   retained: the final manifest supersedes its two-object binding and the
   production graph adapter correctly binds the immutable sidecar directly.
6. **Positional rescue join — repaired.** Settlement first proves that the v1
   sidecar is the deterministic derivative of the supplied capture and its
   exact capture-object identity. It therefore rejects a valid same-slate
   sidecar from another run or capture root before interpreting candidate
   ordinals. Settlement then requires a complete
   one-to-one join on both `candidate_instance_id` and `roster_id`; duplicate,
   missing, extra, or mismatched rows fail before calculation. Input order has
   no effect. Every outcome source, winner source, and winner registry is bound
   to exact provider bytes. Force-one rescue totals remain explicitly non-joint.

## P1 and authority disposition

7. **Selector/source compatibility — preserved.** The adapter consumes current
   typed events and existing `_native_candidate_transform` / `_candidate_capture`
   seams. It does not modify engine, live-lineup, CBWU, selector, immutable v1,
   or graph-v2 sources. The exact v6 inventory remains
   `830dcfbde6cd3e2a6ac629cfbf6a7f8acd2b237f8951f9c050d40a6e1f30ad54`.
8. **Strategy/objective/preset semantics — repaired.** Selector ID and retrieval
   preset ID are separate required fields, and the existing graph-v2 total map
   is used. Admission stage IDs are never substituted for presets.
9. **Execution and model identity — bounded honestly.** The capture binds the exact v6
   policy inventory, a separately hashed 22-file lineage-adapter manifest,
   digest-form image reference, exact source commit, CBC binary hash/size, PuLP
   version, Python/NumPy/OS/architecture/CPU/memory envelope, and exact
   model-registry artifacts. A source run must prove one of two explicit modes:
   an exact globally clean Git checkout, or a Git-free immutable image whose
   embedded `IMAGE_SOURCE_COMMIT_SHA` equals the receipt and whose every
   manifest-bound source file exists and is nonsymlinked. The selected mode is
   persisted in the create-once capture. The local receipt explicitly records
   `provider_execution_identity_verified=false`,
   `provider_resource_envelope_verified=false`, and
   `execution_authority=false`; it cannot be presented as Cloud Run authority.
   Positive CPU and memory values are required. Model generations are frozen before
   generation and exact-reopened after generation; a changed latest week,
   object census, generation, bytes, hash, or creation time fails before the
   first capture can publish.
10. **Read/write boundary — repaired.** GCS publication is fixed to
    `settings.gcs_bucket`, one deterministic run prefix, five fixed names, and
    create-only `if_generation_match=0`. A scoped BigQuery proxy permits only
    one semicolon-free SELECT/WITH statement from the seven frozen pre-lock
    tables, rejects mutation tokens, retains no direct delegate-client field,
    and exposes no write methods. Rejected reads remain fatal even if legacy fallback code catches
    the first exception. Ownership shadow, candidate log, distribution artifact,
    and graph writes are disabled. There is no runtime entry point.
11. **Double salary read — repaired.** One exact latest-pull dataframe supplies
    lock time, allowed player IDs, draftable bridge, salary catalog, and salary
    overrides. A test store raises on a second read; all retries complete with
    exactly one read.
12. **Outcome exclusion and feature intelligence — repaired.** Effective player
    fields use a positive, versioned allowlist, so aliases such as
    `actual_rank` fail rather than escaping a denylist. The exact typed feature
    values and player order—not merely a hash—live in the create-once capture,
    including projection distribution, component means, market blend, salary,
    matchup, ownership-derived pre-lock tilt, and route fields when present.
    Detailed rows remain outside Neo4j; only the bounded graph-v2 aggregate is
    produced.
13. **Settlement authority — preserved false.** Descriptive settlement binds
    candidate scores, opportunity rosters, complete standings, entries/field
    bridge, access receipt, winner score, and winner-registry-v2 identities, but
    it deliberately sets official-adapter, settlement, decision, promotion,
    and graph-mutation authority to false. It cannot support adoption until
    reviewed official source adapters exact-reopen those sources.

The donor's useful paid-preparation seam is also retained as an optional
callback on the existing paid-v2 exporter. Its test proves ordinary and traced
CSV bytes and export receipts are identical. Nothing calls the seam yet.

## Validation

- **158/158 focused compatibility and review-gate tests passed** across
  immutable v1 lineage, typed selector instrumentation, graph-v2, real live
  multiseed/CBWU behavior, policy-v6 identity, generation exposure, paid-v2,
  and all new authority/publication/settlement tests.
- The original new/modified 47-test slice passed independently; the three
  directly affected modules now pass 24/24 after six new adversarial cases.
- Adversarial coverage includes subsecond provider time, create-only GCS race,
  later-clock retry after each of five write boundaries, changed source mode
  and image receipt on partial resume, complete post-lock
  read-only reopen, arbitrary bucket rejection, salary second-read rejection,
  model-generation drift, dirty/wrong source commit, rejected BigQuery reads
  swallowed by caller code, multi-statement and WITH-prefixed write attempts,
  exact-lock salary/outcome timestamps, feature alias rejection, matrix tamper,
  cross-root sidecar/capture joins, keyed score permutation,
  missing/duplicate score rows, an untracked file anywhere in a
  source checkout, and an immutable image with no Git executable.
- The submitting agent's `69488cc2` branch passed Ruff. Ruff is not installed
  in the independent review environment, so no fresh Ruff result is claimed
  for `0c65a3cc`; all affected modules compile and `git diff --check` passes.
- A repository-wide suite was started but intentionally interrupted near 1%
  because this repository includes long-running experiment tests; no failure
  had appeared. It is not counted as validation.

## Remaining operational sequence

These are activation controls, not unresolved implementation defects:

1. Merge the independently reviewed selective branch as inactive infrastructure
   without importing the rejected donor contracts.
2. Add a narrow adapter for the adopted Week-1 `D800_DEMAX` path (single-bank
   800-solve dual-EMAX) or consume its immutable candidate/book artifacts. The
   current runner invokes the legacy five-seed CBWU path and **must not** be
   labelled as the entered D800 book, paid lineage, or Week-1 capture.
3. Add a fixed provider launch contract that binds Cloud Run execution UID,
   job generation, exact image digest, retry/timeout policy, and the provider
   resource envelope; only that contract may upgrade execution authority.
4. Build one immutable image from the exact merged commit, set its embedded
   source revision to that same full commit, and construct its execution
   receipt from the immutable image digest.
5. Well before lock, run exactly one candidate-only D800 shadow with the read-only
   model authority and closed GCS store. A checkout run rejects any dirty tree
   or mismatched commit; the normal Git-free image run rejects a mismatched
   embedded revision or missing manifest-bound source.
6. Exact-reopen the final manifest and all five provider generations, verify
   returned-book parity, and inspect the graph projection offline.
7. Only after that smoke may production choose to load the bounded packet into
   a dedicated shadow graph. Settlement remains descriptive until the official
   standings/entry/winner adapters are separately reviewed.

The branch should not be presented as a deployed Neo4j experience or an active
lineup change. It is the repaired evidence path needed to learn where scoring
opportunities are lost without changing how the book is built.
