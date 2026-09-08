# Week-1 A5 capture-v3 P0 repair independent review

Date: 2026-09-08

Review branch: `codex/week1-capture-v3-p0-independent-review-20260908`

Reviewed handoff tip: `7b24024c96222e5c08ccf8db05fb26e39cf3277d`

Reviewed code/report candidate: `4713cb835bd7e190e1cd1015125bbaeee1f397b5`

Reviewed candidate tree: `e4b42af4347bd44c0cf07764a6e0653077a3ebbd`

Production parent: `03f0ea35183c9523e4a1018ca260b1dabea74514`

## Decision

**P0 HOLD. Do not freeze the live A5 allocation/manifests, claim paid
acceptance, or certify a complete contest field from this candidate yet.**

The repair correctly closes most of the prior code-level defects: it accepts
real min-churn permutations, separates raw and semantic hashes, exact-reopens
all references it is given, pins and rederives the four A5 contest facts,
replays the salary/player/book bridge, and leaves the live allocation pins
absent. Two evidence roots remain assertions rather than observations of
DraftKings. Exact publication makes those assertions immutable, but does not
make them authoritative:

1. `dk-accepted-entry-evidence/v1` is caller-constructed normalized JSON with
   no exact underlying Entry History/API/browser capture; and
2. `dk-final-field-provider-source/v1` is caller-constructed normalized JSON
   containing the asserted displayed size and settled state, not raw provider
   bytes plus a deterministic parser.

Because of the second gap, the original truncated-prefix adversary remains:
a top-N standings CSV can be paired with a newly published wrapper asserting
`displayed_final_field_size=N`; parsed and displayed counts agree and the
candidate can call that prefix a complete underfilled field. The existing test
only checks a top-N CSV against a wrapper claiming `N+1`, so it does not
exercise this attack.

This was a static, outcome-blind review. Per the active serial-lane boundary,
no pytest command ran. The review made no provider, cloud, DraftKings, paid,
score, outcome, deployment, or production-main change.

## Requirement disposition

| Required repair | Static disposition | Evidence |
|---|---|---|
| Min-churn permutations | **PASS** | Prepared `export_ordinal` and `paid_input_book_ordinal` are independent complete domains; realized `(entry_index,lineup_rank)` edges preserve the permutation. The reverse 1/2 fixture is explicit. |
| Raw versus semantic identity | **PASS** | `semantic_sha256` excludes only itself; complete canonical bytes receive independent URI/generation/raw SHA/byte identity and are reopened exactly. |
| Exact-generation reopen of all supplied references | **PASS with source-authority caveat** | Allocation, source manifest/children, template projection, catalog, bridge, books, prepared capture, filled CSV, accepted evidence, manifests, receipts/root, final-field evidence, standings, and normalized field all traverse `read_exact`. The remaining problem is what the two source artifacts actually contain, not whether their generations are reopened. |
| Raw accepted rows | **HOLD** | The accepted rows are parsed from exact bytes, but those bytes are a normalized object built directly by the caller and contain no underlying DraftKings observation identity or parser receipt. |
| Exact A5 facts | **PASS** | Exact IDs, names, fees, capacities, entry limits, K, draft group, lock, prize totals, qualifier/guarantee facts, ticket destinations, terminal manifest, and four child identities are pinned and rederived from the exact contest-detail shape. |
| Complete-field standings prefix | **HOLD** | Raw standings rows/ranks/rosters are parsed and count-matched, but the independently asserted displayed size and settled state are not derived from raw provider bytes. A matching false size still certifies a prefix. |
| Production internal/DK identities and salary bridge | **PASS at the contract layer; operational HOLD** | Exact catalog SHA is recomputed; internal, stable DK, and draftable IDs are one-to-one; book slots, salaries, teams, positions, active state, roster SHA, and lineup ID are replayed. No governed publisher or real-shaped bridge artifact exists yet. |
| Fail-closed live pins | **PASS** | Allocation raw and semantic pins are `None`; `live_capture_pins()` refuses. The lobby projection raw generation is likewise absent rather than invented. |

## Blocking findings

### P0-1: accepted-entry truth is a self-authored normalized assertion

`_parse_accepted_evidence` accepts exactly these semantic fields:
`schema_version`, `complete`, `captured_at`, `contest_id`, `draft_group_id`,
`entries`, and `semantic_sha256`
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1849-1915`). Each entry
contains a caller-supplied `status="accepted"` and roster IDs. The acceptance
builder exact-reopens that object and faithfully projects it
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1987-2007`).

There is no field for an exact Entry History/API/browser observation, no raw
source identity, no source endpoint/method, and no deterministic raw-to-row
parser. The test demonstrates the actual trust boundary by constructing the
accepted rows directly and publishing them as the evidence object
(`tests/test_week1_a5_capture_contracts.py:461-525`). A producer defect can
therefore mark all intended rows accepted even if DraftKings accepted none;
the contract will prove only that the false statement was stored immutably.

This does not undermine the exact prepared capture or filled-upload checks.
Those prove what production intended to upload. They cannot prove what
DraftKings accepted.

Required repair: make the accepted-entry artifact a deterministic projection
of one exact underlying provider observation. Retain both identities:

- exact raw Entry History/API/browser-export bytes plus provider creation time
  and source/method identity; and
- the canonical normalized accepted-row artifact derived only from those
  reopened bytes.

If DraftKings supplies no machine-readable export, use a separately reviewed
operator capture/attestation schema that binds the lossless page evidence and
its extraction, not a free-standing `complete=true/status=accepted` object.
The actual real-shape smoke must establish which fields are truly available;
do not invent roster IDs that Entry History does not expose. Roster truth can
remain joined from the exact filled CSV once accepted Entry IDs/status are
observed authoritatively.

### P0-2: the final-field wrapper can still legitimize a top-N prefix

`_parse_final_field_source` accepts a compact JSON wrapper whose `source`
contains only caller-supplied `contest_id`, `draft_group_id`,
`contest_state="Settled"`, and `displayed_final_field_size`; its endpoint is
also just a string inside that same object
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:2394-2438`).
`build_final_field_evidence_v1` exact-reopens the wrapper and a separately
named standings CSV, then binds them together
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:2441-2488`). The normalized
builder requires parsed CSV rows to equal the wrapper's claimed displayed
size, which is necessary but not sufficient.

The fixture constructs this wrapper directly from its `size` argument
(`tests/test_week1_a5_capture_contracts.py:719-759`). The truncation test asks
the K-row CSV to disagree with a K+1 wrapper, so rejection is expected. It does
not test the unresolved adversary: K-row prefix plus a K wrapper. That pair
passes the same equality while the real contest can contain hundreds of
thousands of entries.

The production `capture-dk-standings` path is stronger about CSV contents,
competition ranks, ownership reproduction, and exact expected count, but its
displayed count is currently an operator argument. The candidate does not add
the provider-source collector/parser or connect to a lossless page capture.

Required repair: preserve exact lossless provider/page evidence for contest
identity, settled state, and displayed final submitted count, and derive the
wrapper fields through reviewed code. Bind that raw provider identity to the
raw standings download in one capture receipt. Add the actual adversary:

1. publish a top-N CSV;
2. publish a normalized wrapper falsely claiming displayed size N; and
3. prove that validation still refuses because no authoritative provider raw
   evidence derives the claim.

The valid path should use the same exact provider observation to bind contest
ID/state/displayed size and the exact downloaded standings identity. An
operator confirmation may authorize collection, but must not itself prove
completeness.

## Additional release risks (non-independent of the HOLD)

### P1-1: real create-once timing semantics need an executable rehearsal

Consumers require allocation/manifest/acceptance/root/final-field/normalized
objects to have provider `created_at` no later than timestamps already sealed
inside those same objects. The synthetic store makes publication time exactly
equal to each declared boundary. A real upload normally receives provider
time only after bytes containing the boundary have been serialized.

This can be valid only if those fields are explicitly prospective cutoffs and
the publisher waits until each cutoff before downstream consumption. That
meaning and wait are not stated. If they are intended observation/publication
times, the inequality is reversed and the live chain is not executable
without backdating or guessing a future timestamp. The governed publisher and
real-object smoke must settle this before release; add strict-before/after
fixtures rather than equality-only fixtures.

### P1-2: real accepted-entry and standings shapes remain untested

The candidate correctly records this operational gate. In particular, the
real DK acceptance surface may not expose ordered draftable IDs, and a real
qualifier `Prize`/`Winnings` representation may differ from the synthetic
split. The source-authoritative repairs above should be driven by redacted
real shapes before freezing a successor schema.

### P1-3: shadow settlement is still absent

The owner-approved A5 decision requires P_CTRL, D400_DEMAX, and D800_WEMAX to
be graded at K57/K20/K3/K10 against the same captured field. This candidate
binds their pre-lock book edges but deliberately does not settle/grade them.
That remains visible P1 work and must not be lost after the raw evidence roots
are repaired.

## Properties that should be retained

- Keep the independent min-churn bijections; never restore
  `entry_index == lineup_rank`.
- Keep semantic SHA separate from exact serialized-object identity.
- Keep every generation-exact reopen and provider-time check.
- Keep the code-pinned terminal contest source and exact four A5 facts.
- Keep the complete salary/bridge/book replay and canonical lineup identity.
- Keep distinct advertised/current/final field counts.
- Keep signed fantasy points, exact competition ranks, exact tie-cent pooling,
  and separate cash/ticket reconciliation.
- Keep legacy v2 explicitly fixture-only for live A5.
- Keep live pins absent until the missing real artifacts are published and
  independently authenticated.

## Static validation performed

- Exact remote handoff tip resolved to
  `7b24024c96222e5c08ccf8db05fb26e39cf3277d`.
- Candidate identity and full changed code/tests/docs/reports were inspected.
- The five local outcome-blind contest-source copies match the identities
  reported by the candidate; their relevant source shapes were inspected.
- Python compilation of the changed module and focused test module: **PASS**.
- `git diff --check` over production parent through reviewed handoff tip:
  **PASS**.
- Ruff was not installed in the available production virtual environment; the
  candidate's recorded Ruff pass was not independently reproduced.
- Pytest: **not run**, by explicit serial-lane instruction.

Because there are blocking static findings, no serial pytest window is being
requested for a terminal PASS. The next safe action is a bounded successor
that anchors accepted-entry and displayed-final-size claims to exact raw
provider observations, followed by independent static review, a real-shape
smoke, the 832,342-row scale rehearsal, and then the focused serial suite.

