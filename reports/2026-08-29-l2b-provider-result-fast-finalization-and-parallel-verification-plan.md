# L2b provider-result fast finalization and parallel verification plan

Date: 2026-08-29

## Decision

Use the explicit `collect-provider-results` path for the already-completed L2b
54-task execution. The 54 Cloud Run tasks already performed the expensive
selector construction independently and in parallel. A second serial rebuild
of every selector on the workstation is not required to establish a gradeable
terminal.

The fast path is outcome-blind. It must observe the exact provider execution as
54 succeeded, zero failed and zero cancelled before it opens any scientific
result. It then generation-exact opens all 54 fixed result URIs, validates the
complete persisted-result law against each exact projection, validates all 54
normalized lineup/population/book surfaces, and publishes a **distinct,
explicitly provisional** provider-result terminal. It never writes the
canonical `terminal-selector-root.json` owned by the active exact-replay
collector.

The provisional realized grader likewise exact-opens the terminal root, manifest,
projections and all 54 immutable results and reruns normalized gradeability,
but does not recompute selectors or reopen world matrices. The outcome reader
remains unreachable until that entire outcome-free graph passes. Its result is
descriptive/provisional only: confirmatory, promotion and production authority
are all false until the asynchronous canonical replay completes.

## Immediate command

After focused tests pass, the existing request can be reused without changing
the provider execution or its task results:

```bash
.venv/bin/python scripts/run_corpus_r6_l2b_selector_adapter_v1.py \
  collect-provider-results \
  --request-file /tmp/r6-l2b-full54-7f553e12-v1/full54-collect-request.json \
  --output-file /tmp/r6-l2b-full54-7f553e12-v1/full54-provider-collect-result.json
```

This command performs one create-once write only after validation:
`provisional-provider-terminal-selector-root.json`. It cannot collide with or
change the active legacy collector's fixed `terminal-selector-root.json`.

Then build a grade request using the returned provisional terminal identity,
the frozen outcome-snapshot identity, and this exact output URI under the same
run prefix:

`provisional-provider-realized-grade.json`

The following creates the required canonical, no-trailing-newline request from
the collect result and the already-frozen outcome identity:

```bash
jq -cS \
  --argjson outcome '{"bytes":3547704,"generation":"1787987566557209","sha256":"96c88d27cfa356794e250431dbcaa638fe7df2ec8dc1a9ead8538f0608c32f88","uri":"gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-catalog-wide-realized/20260829-score-sprint-c9f12ed7-catalog-outcomes-v1/outcome-snapshot.json"}' \
  --arg output_uri 'gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-l2b-selector/20260829-score-sprint-6c9cfd70-diversity-v1/provisional-provider-realized-grade.json' \
  '{outcome_snapshot_identity:$outcome,output_uri:$output_uri,terminal_root_identity:.terminal_root_identity}' \
  /tmp/r6-l2b-full54-7f553e12-v1/full54-provider-collect-result.json \
  | perl -0pe 's/\n\z//' \
  > /tmp/r6-l2b-full54-7f553e12-v1/provisional-grade-request.json
```

Run:

```bash
.venv/bin/python scripts/run_corpus_r6_l2b_selector_adapter_v1.py \
  grade-provider-results-provisional \
  --request-file /tmp/r6-l2b-full54-7f553e12-v1/provisional-grade-request.json \
  --output-file /tmp/r6-l2b-full54-7f553e12-v1/provisional-grade-result.json
```

## Evidence retained

- The fixed manifest's exact build receipt, source commit, immutable image,
  job name and job UID bindings.
- The exact Cloud Run execution name and terminal 54/54 status, with no log,
  scientific-output or outcome inspection used to establish success.
- The validated launch result and complete provider execution-status record are
  embedded in the provisional terminal root, including execution name,
  provider UID/generation, task counts and status self-hash. Missing, tampered
  or nonterminal execution evidence fails before any result is opened.
- One fixed result URI per manifest ordinal and the exact GCS generation,
  byte length and content SHA-256 discovered only after provider terminality.
- Canonical JSON, the complete result self-hash, exact ordinal/slate binding,
  exact manifest identity/hash, L2b panel identity/hash, L2b source-task
  identity/hash, projection identity/hash and later-source identity.
- Full `validate_slate_result_v1` checks against the exact projection,
  including candidate rows, nested selector-result shapes/hashes, selected
  prefix/book derivations and normalized population/book equality.
- Full 54-slate external normalized-terminal validation: lineup-to-roster
  identity, roster hashes, unique coordinates, population membership, exact
  entry budgets and coordinate coverage across every slate.
- A provisional terminal root built only after all 54 results pass, with the
  same exact result descriptors but an intentionally different schema, URI and
  authority tier from the canonical deep-replay terminal.
- The no-outcome boundary: collection accepts no outcome identity or reader;
  grading does not invoke its separately supplied outcome reader until the
  terminal and normalized surfaces pass.

## Evidence not retained by the immediate fast path

The fast collector does not reconstruct the score matrices from the L2b world
artifacts and rerun every selector centrally. Therefore it does not provide a
second observation of deterministic reproducibility for each task result.

This is a narrow loss, not a loss of primary computation evidence. Every
provider task already opened the frozen panel/projection/world/source graph,
built and structurally validated its selector result, published it
create-once, and exact-reopened the published bytes before returning success.
The legacy collector repeats the same implementation, not an independent
implementation. Repetition can detect nondeterminism or a transient compute
fault, but it cannot detect a deterministic algorithm defect that the task and
collector share. Content identities detect drift relative to the retained
objects; hashes alone do **not** exclude a coherent substitution of a complete
graph by an authority with write capability. This is why the fast grade stays
provisional until source/science replay completes.

Keep the active legacy `collect` / `finalize` path as the asynchronous
confirmatory audit. It alone may publish the canonical terminal. It does not
block descriptive historical scores, but its result governs any confirmation,
promotion or production decision.

## Reusable parallel-verification successor

For future experiments, restore the reproducibility check without serial wall
time:

1. Freeze a verification manifest that binds the selector manifest, all 54
   provider result identities, verifier build/source/image/job authority and
   one fixed receipt URI per ordinal. It accepts no outcome input.
2. Launch one reused Cloud Run Job with 54 tasks. Each task exact-opens one
   result and its projection/world/source inputs, performs the existing exact
   selector replay, and publishes a compact create-once verification receipt.
3. Each receipt binds ordinal, slate, manifest identity/hash, result
   generation/content identity and self-hash, projection identity/hash, L2b
   source-task identity/hash, verifier code/image identity, normalized-surface
   hash, and explicit false outcome/promotion fields.
4. After provider 54/54 success, a tiny reducer exact-opens the verification
   manifest, 54 receipts and 54 result identities, validates the normalized
   surfaces, and publishes the terminal root last. It performs no selector
   computation.
5. The grader consumes receipt-bound results and normalized surfaces. It never
   reopens worlds or reruns selectors before scoring.
6. In the next selector runtime revision, publish the same receipt inline at
   the end of each original task. The task already holds the freshly computed
   expected result and exact-reopens the create-once object, so future panels
   require no separate verification execution at all.

The expected critical path becomes the slowest single slate plus terminal
aggregation, rather than the sum of 54 slate replays. The existing full54
execution demonstrates that this work parallelizes successfully on Cloud Run.

## Regression gates

- Fast collection cannot open a result before exact provider 54/54 success.
- There is no public low-level provider finalizer; the only CLI publication
  path is the provider-status-gated `collect-provider-results` command.
- Missing or tampered launch/status evidence fails root validation; the root
  durably binds the observed execution name, UID, generation and status hash.
- Duplicate identities or URIs fail before terminal publication.
- Any root/manifest/result/projection/L2b/later-source binding drift fails.
- World loaders, scoring-player reconstruction and selector replay are not
  called by fast collection or post-terminal grading.
- Normalized lineup/book validation runs across exactly 54 ordered slates.
- Any normalized validation failure occurs before the first outcome read.
- The legacy deep collector remains unchanged, owns a disjoint canonical URI,
  and is the only current confirmatory path.
