# Week-1 A5 capture-v3 independent static review

Date: 2026-09-08  
Reviewer branch: `codex/week1-capture-v3-independent-review-20260908`  
Candidate branch: `codex/week1-capture-v3-20260908`  
Candidate commit: `58b7c98bccdbabff54c530ba515d14b22533e977`  
Candidate tree: `233e33a65d1b973adf5ff8d705bc9a75c1db4009`  
Supplied series base: `b8768e497d7e72033e8c5d880a5199b03fb2e545`  
Candidate direct parent: `e6422990eddf8b4612fcf4bd4d66c3eaf48466b9`

## Decision

**P0 HOLD. Do not use this candidate to freeze Week-1 A5 manifests, prove paid
acceptance, or claim complete-field settlement.**

The candidate has a useful schema outline, especially its distinct advertised,
current, and final field-count fields. It is not yet an immutable evidence
contract. A valid production min-churn fill is rejected, raw-object identity is
conflated with an artifact's semantic self-hash, referenced objects are never
generation-exactly reopened, the known four-contest A5 identity is not pinned,
and settlement can certify a caller-supplied truncated field.

This was a static review. Per the assigned serial-lane boundary, the reviewer
ran no pytest invocation or broad test. No cloud, DraftKings, paid-entry,
deployment, or `main` state was read or mutated by the review.

## Scope and candidate identity

The reviewed tree exactly matches the supplied candidate. The supplied
`b8768e49...` value is the two-commit series base, not `58b7c98b...`'s direct
parent: the series is `b8768e49 -> e6422990 -> 58b7c98b`. The candidate changes
only the v3 docs/report/module/tests plus `HANDOFF.md`; the legacy v2 Python
implementation is unchanged.

The review checked the candidate against:

- the frozen K57/K20/K3/K10, $449 allocation and required paid/shadow edge
  semantics in `reports/2026-09-03-a5-week1-contest-allocation-decision.md:10-53`;
- the exact live contest IDs, names, capacities, limits, templates, qualifier
  facts, payout/ticket evidence, and pinned contest-detail source manifest in
  `reports/2026-09-04-week1-a5-live-contest-capture.md:9-37` and
  `reports/2026-09-04-week1-a5-live-contest-capture.md:78-141`;
- the raw content-identity, real-artifact smoke, launcher-lane, handoff, and
  point-in-time rules in `CLAUDE.md:41-87`; and
- the production paid fill, full-field capture, and existing shadow-field
  bridge.

## Findings

### P0-1: acceptance rejects a valid min-churn paid fill

The production paid exporter deliberately permits the reviewed min-churn
assignment to permute ranked input lineups across DraftKings entry rows:

- `src/nfl_dfs/optimizer/export.py:116-148` computes a Hungarian assignment and
  returns the selected lineup index for each entry row.
- `src/nfl_dfs/optimizer/paid_classic_book_v2.py:553-597` invokes that filler and
  proves only that the exact validated roster set appears once; it does not
  require input rank to equal output row ordinal.
- Its prepared evidence therefore records `export_ordinal` and
  `paid_input_book_ordinal` independently at
  `src/nfl_dfs/optimizer/paid_classic_book_v2.py:612-640`.
- Existing adversarial coverage demonstrates the intended reverse assignment:
  entry 1 receives lineup B and entry 2 receives lineup A in
  `tests/test_export_entries.py:22-36`.

The A5 allocation initially records `entry_index == lineup_rank` at
`src/nfl_dfs/inference/week1_a5_allocation.py:192-218`. The candidate correctly
derives entry index from export ordinal and lineup rank from paid-book ordinal
at `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1039-1087`, but then keys
the old allocation edge by entry index and requires that edge's original rank
to equal the post-fill rank at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:895-911`. Any non-identity
min-churn permutation consequently fails after an otherwise valid fill.

The new fixture hides the incompatibility by setting
`paid_input_book_ordinal == export_ordinal` for every row at
`tests/test_week1_a5_capture_contracts.py:218-228`.

Impact: the contract can reject truthful evidence only after the owner has
performed a paid, time-sensitive action, preventing the four-contest root from
being completed. The acceptance edge must record the realized bijection
`(entry_index, lineup_rank)` rather than demand that it remain the allocation's
identity permutation.

### P0-2: semantic self-hashes cannot serve as raw object hashes

`_finish` computes each semantic artifact hash over the body *before* adding
the hash field, and `_self_hash` validates the same projection:
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:169-182`. That is a reasonable
semantic hash law. It is not the SHA-256 of the serialized object, whose bytes
include the hash field.

The candidate nevertheless requires a GCS object's raw `sha256` to equal that
semantic self-hash:

- manifest identity: `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:725-731`;
- allocation identities in a manifest and acceptance:
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:510-522` and
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:777-795`;
- per-contest acceptance receipt identities:
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1171-1175`; and
- allocation/root identities at settlement:
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1418-1427`.

An honestly published canonical JSON object includes its semantic hash field,
so its byte SHA is not that hash-under-exclusion. Satisfying both would require
an infeasible SHA-256 fixed point/preimage, or lying about the raw object
identity. The repository's actual identity primitive hashes the exact raw
bytes and records URI, generation, bytes, and digest independently at
`src/nfl_dfs/research/object_identity.py:29-68`.

The tests do not exercise publication. They fabricate ten-byte identities
whose digest is copied from the semantic hash at
`tests/test_week1_a5_capture_contracts.py:30-38`,
`tests/test_week1_a5_capture_contracts.py:131-132`,
`tests/test_week1_a5_capture_contracts.py:205-206`, and
`tests/test_week1_a5_capture_contracts.py:285-287`.

Impact: real manifests, allocations, acceptances, and roots cannot satisfy the
advertised identity contract. Semantic SHA and raw-object content identity
must be distinct fields with distinct validation laws.

### P0-3: identities are dangling claims; no provider-exact reopen binds evidence

The new module says it performs no storage operation
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1-7`). `_identity` only checks
the syntax of caller-supplied URI/generation/SHA/bytes
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:126-149`). There is no store
or `read_exact` boundary anywhere in the module.

As a result:

- Manifest facts and payout rows are not parsed from the four named source
  objects. The code merely normalizes source identity/timestamp dictionaries
  and compares their caller-supplied capture times at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:455-492`.
- Book identities are not tied to the inline book entries. `_book_binding`
  accepts the artifact identity and separately hashes the supplied entries at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:312-363`.
- Prepared evidence is compared to `canonical_sha256(prepared)`, and the filled
  identity is compared to SHA/byte values repeated inside that supplied object,
  but neither raw object is opened at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:969-989`.
- Acceptance evidence is especially unbound: the raw identity is accepted at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1098-1100`, while a
  separately supplied row projection is hashed at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1101-1126`. There is no
  parser or equality connecting those rows to those bytes. The passing fixture
  explicitly gives this identity an unrelated digest at
  `tests/test_week1_a5_capture_contracts.py:251-265`.
- All pre-lock times are caller text. The identity omits provider creation time,
  so a post-lock object can be backdated. The `outcome_fields_read=[]` field is
  likewise an assertion, not a property of reopened bytes.
- Settlement validation just replays separately supplied rows
  (`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1475-1547`).

The repository already has the required pattern: create-once publication,
generation-conditioned download, raw SHA/byte verification, and provider
`time_created` capture in
`src/nfl_dfs/inference/prospective_generation_shadow_operator.py:222-312`.
The candidate does not use it or an equivalent interface.

Impact: nonexistent generations, wrong bytes, stale facts, cross-contest
sources, fabricated acceptance evidence, and post-lock publications can all be
presented as valid evidence. Syntax validation and semantic replay of caller
objects do not establish immutable provenance or the point-in-time boundary.

### P0-4: the known A5 contest identity and allocation root are not frozen

The candidate constants pin only role K values, policy names, and slate ID at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:30-44`. Contest facts are
accepted from `week1-a5-contest-allocation/v1`, whose role constants pin only K
and fee (`src/nfl_dfs/inference/week1_a5_allocation.py:20-30`). Its normalizer
accepts any unique numeric contest ID, any nonempty name, and almost any
capacity/limit at least K at
`src/nfl_dfs/inference/week1_a5_allocation.py:124-189`. The v3 manifest then
checks only that it mirrors that dynamically supplied allocation at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:455-471`.

The new tests demonstrate the defect: they use the right IDs but fake contest
names and capacities `60/25/5/12`, and those fixtures are intended to validate,
at `tests/test_week1_a5_capture_contracts.py:18-23` and
`tests/test_week1_a5_capture_contracts.py:45-62`.

The actual frozen facts are already known:

- IDs/capacities/limits are `193028206/832342/150`,
  `193028208/158541/20`, `194478066/5000/150`, and
  `194478065/17835/150` in
  `reports/2026-09-04-week1-a5-live-contest-capture.md:15-24`.
- Template IDs and qualifier/ticket descriptions are recorded at
  `reports/2026-09-04-week1-a5-live-contest-capture.md:26-37`.
- The create-once contest-detail manifest and four exact source identities are
  recorded at `reports/2026-09-04-week1-a5-live-contest-capture.md:99-141`.

Neither that terminal source-manifest identity nor one exact live A5 allocation
semantic root/raw identity is pinned. Template ID, qualifier status, guarantee
status, and exact ticket terms are also absent from the v3 contest schema.

Impact: a new self-consistent allocation over the wrong four contests can pass
with the same A5 allocation ID and K/spend totals. That violates the operator's
explicit no-silent-substitution boundary in
`reports/2026-09-03-a5-week1-contest-allocation-decision.md:40-53`.

### P0-5: settlement can certify a truncated or cross-wired field as complete

The settlement accepts `observed_final_field_size`, `confirm_settled`, and
`confirm_full_field` directly from its caller
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1334-1369`). It proves only
that the separately supplied row count equals that caller-supplied size
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1290-1317`). Underfill is
explicitly allowed whenever that size is below advertised capacity.

The normalized rows contain only entry ID, rank, points, and cash payout; they
contain no contest identity, raw-row provenance, roster, or settled-time field
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1290-1313`). The normalized
identity is checked against a semantic row hash but never reopened, while the
raw standings identity is only copied into the receipt at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1374-1379` and
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1446-1450`. Paid reconciliation
requires only that accepted IDs are a subset of those rows
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1412-1417`).

Therefore a top-N/cross-wired file containing the accepted IDs can be declared
to have final size N and pass as an underfilled complete field if its ranks and
payouts are internally plausible. The booleans do not close that proof gap.

The production capture parser does perform stronger raw-byte, expected-count,
Entry-ID, roster, settled-time, competition-rank, and ownership checks at
`src/nfl_dfs/ingest/ownership_import.py:301-378`. However, its apply path
archives `source.csv` and `receipt.json` without returning GCS generations or
publishing the generation-pinned canonical normalized standings object the v3
runbook assumes (`src/nfl_dfs/ingest/ownership_import.py:618-757`). The runbook
then tells the operator to construct v1 against a "generation-pinned normalized
capture" at `docs/week1-a5-capture-contract-v3.md:168-184`, but the candidate
adds no publisher/adapter that creates it.

Impact: `full_field_confirmed=true` is not an evidence-backed completeness
claim. This must be repaired before v1 settlement can be treated as durable
scientific evidence.

### P1-1: book rows do not prove canonical lineup or player-bridge identity

`_book_entry` checks that each internal and DraftKings list has nine unique IDs
and that `roster_sha256` hashes the internal list, but it only regex-checks
`lineup_id`; it never requires
`lineup_id == "lineup-v1-" + roster_sha256`, never reopens the book, and never
proves the internal-to-draftable mapping, positions, salary, slate membership,
or DK legality (`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:280-309`).
The canonical production law does bind lineup ID to roster membership at
`src/nfl_dfs/inference/week1_participation_mixture.py:527-542`.

The fixture constructs lineup IDs, internal IDs, and draftable IDs from three
independent formulas and supplies an unrelated artifact identity at
`tests/test_week1_a5_capture_contracts.py:135-156`; it still passes the intended
path. `salary_catalog_sha256` is accepted from prepared evidence at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:960-982` but is not connected
to a reopened manifest/book/player bridge.

Impact: a syntactically correct but unrelated or illegal roster materialization
can be described as the frozen book.

### P1-2: final roster/late-swap and the required shadow grades are absent

The allocation decision requires P_CTRL, D400_DEMAX, and D800_WEMAX at the same
K to be graded against the same captured contest field
(`reports/2026-09-03-a5-week1-contest-allocation-decision.md:40-49`). The
candidate pre-lock manifest carries 270 shadow edges, but settlement accepts no
shadow rosters/scores and emits no shadow mapping or grade; its complete output
shape is only the summary at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1428-1472`.

Because normalized standings discard rosters and reconciliation checks only
Entry-ID inclusion, settlement also cannot prove whether each accepted roster
remained final or record a lawful late-swap transition. The existing bridge
already demonstrates the needed same-field roster and shadow mapping shape at
`src/nfl_dfs/inference/prospective_generation_shadow_field_bridge.py:745-877`;
the candidate does not connect A5 to it.

Impact: the final paid result is not joined back to the accepted roster, and a
core frozen A5 counterfactual deliverable is missing.

### P1-3: payout/underfill logic is not authoritative for the two qualifiers

The pre-lock underfill policy is caller-selected from two strings at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:446-454`; it is not derived
from a reopened contest guarantee/rules source. `award_label` is retained in
the ladder at `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:217-259` but
settlement reconciles only numeric `payout_micro` and never checks the award
label or ticket destination/quantity.

That is material for the two qualifiers: the live evidence names two eligible
FFWC ticket destinations and one first-place seat plus cash at
`reports/2026-09-04-week1-a5-live-contest-capture.md:99-117`.

The numeric tolerance is also too loose as a field invariant. Each score group,
including untied entries, receives a one-cent residual, and the total may differ
by `final_size * one cent` at
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1388-1411`. For the 832,342
capacity contest that upper bound is $8,323.42. Conversely, the code requires
all tied rows to have exactly equal displayed payouts, so it cannot represent
an explicitly sourced cent remainder allocated across tied entries.

Impact: a materially wrong total or missing noncash championship award can be
certified as reconciled, while some legitimate official rounding forms can be
rejected.

### P1-4: the operational path is not executable and bypasses the required lane

The documentation accurately admits that there is no governed A5 publisher or
materializer for steps 2-8 at
`docs/week1-a5-capture-contract-v3.md:132-156`, and the implementation report
lists the same blocker at
`reports/2026-09-08-week1-a5-capture-v3-implementation.md:96-120`. A static
reference scan finds the new builders only in this module, its focused tests,
and documentation; there is no CLI/runtime caller.

The refresh runbook directly invokes nine shared Cloud Run jobs with `gcloud
run jobs execute` at `docs/week1-a5-capture-contract-v3.md:100-124`. Repository
law requires the complete shared-job launch chain to acquire the job lane via
`scripts/launcher_registry.sh run` (`CLAUDE.md:68-74`). The runbook also does
not pin and authenticate each job's accepted image/revision or record terminal
execution counters.

Finally, the candidate reports synthetic focused tests but no outcome-blind
smoke against the real contest-detail artifacts and production prepared-entry
shape. That smoke is mandatory before freezing a receipt protocol under
`CLAUDE.md:44-48`.

Impact: even after code repair there is no governed, receipted command that can
produce the described chain safely before lock.

### P1-5: the additive v2 live instructions are contradictory under underfill

The edited rehearsal document says live A5 must follow both v2 and v3 and must
not overwrite v2 capacity with final size
(`docs/week1-contest-capture-rehearsal.md:8-12`). Its unchanged v2 live procedure
still instructs an operator to create the v2 manifest pre-lock and then validate
the real final field against it
(`docs/week1-contest-capture-rehearsal.md:60-116`).

V2 has one `field_size`, treats it as the contest metadata/payout bound
(`src/nfl_dfs/ingest/contest_capture_rehearsal.py:250-348`), and later requires
the production parser's exact observed row count to equal the same field
(`src/nfl_dfs/ingest/contest_capture_rehearsal.py:688-708`). An underfilled
contest cannot keep an immutable pre-lock capacity and also make that single
field equal the final submitted count.

Impact: v2 source compatibility is preserved, but the combined live runbook is
not executable without mutating history or failing. V2 should be explicitly
fixture/legacy-only for live A5, or a narrow immutable adapter must state which
v3 facts replace its ambiguous field.

### P2: additional fail-closed gaps

- Correction lineage validates only revision syntax, a predecessor-shaped SHA,
  and a reason at `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:185-198`.
  It does not reopen the immediate predecessor, require revision increment by
  one, or prove same-contest continuity. The focused test checks only `None`,
  not a fabricated well-formed predecessor, at
  `tests/test_week1_a5_capture_contracts.py:341-353`.
- Point-in-time classification uses URI substring tokens at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:48-56` and
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:152-156`. This can reject a
  legitimate pre-lock payout source merely because its path contains
  `/payout`, while accepting outcome bytes under an innocuous name. Content and
  provider creation time, not path spelling, must establish the boundary.
- `points_micropoints` uses the general nonnegative integer validator at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1290-1312`, so a valid
  negative final fantasy score is unrepresentable.
- Payout normalization expands every tier into a Python dictionary entry per
  advertised rank at `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:244-258`.
  The real Milly has 832,342 places; no real-scale smoke establishes acceptable
  memory/runtime behavior.

## Properties worth retaining

These are useful parts of the candidate and should survive the repair:

- The K57/K20/K3/K10 paid counts, 90-entry total, three same-K shadow policies,
  and 270 shadow edges are structurally explicit.
- The pre-lock schema separates `advertised_field_capacity` from
  `entries_observed_at_freeze`, and only settlement has
  `observed_final_field_size` (`docs/week1-a5-capture-contract-v3.md:21-34`).
- The four-contest root requires all roles and 90 globally unique Entry IDs at
  `src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1148-1219`.
- Builders are default-off and contain no external mutation.
- Legacy v2 Python and fixtures are untouched by the candidate.

These structural properties do not compensate for the P0 provenance and paid
mapping failures.

## Bounded repair contract

The following is the minimum repair boundary for reconsideration. It does not
authorize a scoring, generation, selection, cloud, or paid-entry change.

### 1. Separate semantic identity from raw-object identity

1. Retain an artifact-level semantic hash, explicitly named
   `semantic_sha256`, computed over the canonical semantic body with that field
   excluded.
2. Serialize the complete artifact, including `semantic_sha256`, to canonical
   bytes. Publish those bytes create-once. Record the resulting external
   `artifact_identity = {uri, generation, sha256, bytes}` where SHA/bytes are
   computed over the exact serialized bytes.
3. Never require `artifact_identity.sha256 == semantic_sha256`. On reopen,
   first verify URI/generation/raw SHA/bytes, parse those exact bytes, then
   recompute and verify `semantic_sha256`.
4. Keep an artifact's raw identity outside its own hashed bytes (in the parent
   artifact or publication receipt), avoiding self-reference.

### 2. Require exact provider reopens and enforce point-in-time from metadata

1. Add/inject one `ImmutableObjectStore`-style boundary with generation-exact
   `read_exact`, using the already reviewed pattern in
   `prospective_generation_shadow_operator.py`.
2. Every allocation, contest source, book, prepared capture, filled CSV,
   acceptance evidence object, manifest, acceptance receipt/root, raw standings,
   normalized standings, and correction predecessor must be reopened at its
   exact generation and verified by raw SHA/bytes before its semantics are used.
3. Preserve provider `time_created`/`created_at` in reopen receipts. For all
   pre-lock sources and artifacts, require provider creation strictly before
   lock and no later than the declared freeze/acceptance time. A caller timestamp
   alone is insufficient.
4. Remove URI-token outcome classification as an evidence gate. Parse only
   allowlisted pre-lock schemas/projections from verified bytes; reject outcome
   fields by schema/content.

### 3. Pin the exact live A5 constants and terminal root

1. Define one immutable role table containing exact contest ID, exact name,
   draft group, slate, fee, capacity, limit, lock, template ID, qualifier flag,
   guarantee/underfill authority, and required ticket terms for all four known
   contests.
2. Pin and reopen the exact contest-detail source manifest
   `gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/contests/a5/20260904T105535Z/manifest.json`
   generation `1788519340044066`, bytes `2664`, SHA-256
   `28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4`,
   plus its four child source identities. Re-derive every pinned contest fact
   from those bytes.
3. After the exact contest-ready books exist, publish and independently reopen
   one allocation artifact and pin both its `semantic_sha256` and distinct raw
   `artifact_identity` as the only accepted A5 root. Reusing the allocation ID
   with a different semantic root must fail.
4. A material live change requires a separately authorized replacement-decision
   artifact; it must not be silently accepted by relaxing constants.

### 4. Bind books and player materialization to reopened bytes

1. Derive inline book rows from exact reopened book/materialization bytes; do
   not accept an identity and independent rows.
2. Re-enforce the canonical law
   `lineup_id == "lineup-v1-" + sha256(canonical internal roster)`.
3. Reopen and pin the salary catalog/player bridge, prove a one-to-one mapping
   from every internal player ID to each ordered DK draftable ID, and replay
   roster slots, salary cap, positions, active/slate membership, and exact K.

### 5. Make acceptance a raw-evidence projection and support permutation

1. Publish/reopen the exact `paid-entry-capture/v1` bytes, exact filled CSV
   bytes, and raw Entry History/accepted-entry evidence bytes before lock.
2. Parse the accepted-entry projection deterministically from that reopened raw
   evidence. Store/recompute its projection hash and require exact equality to
   the receipt rows; an unrelated evidence identity must fail.
3. Treat `export_ordinal -> entry_id` and
   `paid_input_book_ordinal -> lineup_rank` as independent bijections. Require
   complete unique coverage of entry indices 1..K and ranks 1..K, and bind each
   realized `(entry_index, lineup_rank, lineup_id, roster)` edge. Do **not**
   require `entry_index == lineup_rank` after min-churn assignment.
4. Add the production reverse-assignment adversary: two entry rows currently
   closest to books B/A must yield valid realized edges `(1,2)` and `(2,1)` and
   a valid acceptance receipt/root. Also test duplicate/missing ranks and a
   fabricated accepted projection against genuine raw evidence.

### 6. Bind complete settlement and shadow grades to one exact field

1. Extend/integrate `capture-dk-standings` so create-once apply publishes both
   the exact raw CSV and one canonical normalized complete-field artifact, and
   returns generation/bytes/SHA plus provider creation time for each and its
   receipt. Reopen all three exactly.
2. Derive contest ID, settled state/time remaining, final row count, Entry IDs,
   ranks, scores, payouts, and final rosters from those exact bytes. The
   displayed final-size evidence and raw parsed count must agree; caller
   confirmation booleans may authorize the action but cannot prove the facts.
3. Join every accepted Entry ID to its final roster. Either require equality or
   bind an explicit validated late-swap transition to separately frozen
   post-acceptance evidence.
4. Grade P_CTRL, D400_DEMAX, and D800_WEMAX at K57/K20/K3/K10 from the same
   normalized field and one exact realized-score source. Preserve the complete
   roster/membership/shadow mapping in the settlement lineage.
5. Derive underfill behavior from reopened guarantee/official-rule evidence.
   Represent cash and noncash ticket awards separately, including destination
   and quantity. Reconcile exact field totals with only mathematically necessary
   rounding residue, not `field_size * one cent`, and explicitly support the
   official tie remainder law.

### 7. Supply the governed operator and release gates

1. Implement one repository-owned, default-off publisher/CLI that constructs,
   publishes create-once, reopens, and receipts the exact four-book allocation,
   four manifests, acceptance chain, and settlement adapters. Manual JSON
   stitching is not an accepted fallback.
2. Rewrite job execution examples to acquire each shared job lane through
   `scripts/launcher_registry.sh run`, use one authenticated immutable image,
   and record exact execution IDs, terminal task/retry counters, and source
   identities.
3. Before freezing any repaired schema, run the required outcome-blind smoke
   against the real pinned contest-detail sources and a representative real
   production prepared-entry/filled-CSV/Entry-History shape. Separately run a
   realistic 832,342-row scale rehearsal without reading Week-1 outcomes.
4. Keep v2 tests/source unchanged, but mark its live `field_size` procedure
   legacy/fixture-only for A5 or provide a reviewed immutable v2-to-v3 adapter.

## Minimum adversarial release matrix

In addition to existing syntactic tests, the repaired suite must demonstrate:

- raw SHA differs from semantic SHA but both verify through exact reopen;
- wrong generation, bytes, raw SHA, missing object, and post-lock provider
  creation time each fail;
- semantic rows paired with another source object's identity fail;
- acceptance evidence raw bytes paired with a fabricated projection fail;
- exact reverse min-churn `(entry_index, lineup_rank)` permutation passes, while
  duplicate/missing ranks fail;
- every wrong contest ID/name/cap/limit/template/qualifier/ticket fact and every
  alternate allocation root fail;
- a truncated top-N file cannot masquerade as underfill, and a source for one
  contest cannot settle another;
- accepted-to-final roster drift fails unless an exact validated late-swap
  transition is present;
- all three shadow books are graded against the same field/root;
- qualifier tickets, official underfill, cent remainder, and negative fantasy
  scores have explicit correct fixtures; and
- a well-formed but fabricated correction predecessor fails exact reopen and
  lineage continuity.

Until those gates pass independent review, the safe operational state is
**HOLD before any A5 manifest freeze or paid upload**.
