# Week-1 A5 capture-v3 P0 repair

Date: 2026-09-08
Branch: `codex/week1-capture-v3-p0-repair-20260908`
Disposition: **implementation candidate; operational HOLD**

## Scope and outcome

This is the bounded repair requested by the independent HOLD report at
`reports/2026-09-08-week1-a5-capture-v3-independent-review.md`. It changes
only capture evidence contracts, focused adversarial tests, and their
documentation. It does not change scoring, lineup generation, selection,
paid-entry behavior, deployment, or production state.

The unsafe v1 acceptance/root/settlement builders now fail explicitly. Their
v2 successors consume semantics only after generation-exact raw reopens.
Legacy contest rehearsal v2 source remains unchanged.

## Repair against the P0 findings

### Min-churn permutation

Acceptance independently proves these complete domains:

```text
export_ordinal 0..K-1 -> entry_index 1..K -> exact Entry ID
paid_input_book_ordinal 0..K-1 -> lineup_rank 1..K -> exact lineup/roster
```

It records the realized `(entry_index, lineup_rank)` bijection. It does not
require equality between those values. The focused fixture reverses the first
two assignments and builds a valid per-contest receipt and 90-entry root;
duplicate/missing/fabricated mappings fail against the raw prepared capture.

### Semantic and raw identities

Every semantic artifact contains `semantic_sha256`, computed without that one
field. Complete canonical bytes—including the field—are published create-once
and receive a separate `{uri,generation,sha256,bytes}` identity. Exact reopen
validates provider identity, raw bytes/SHA/length, canonical JSON, and semantic
hash in that order. The focused fixture asserts that an honest self-hashed
JSON artifact's raw SHA differs from its semantic SHA while both verify.

### Exact reopens and time boundary

One injected `ImmutableObjectStore` protocol is the only object boundary.
Allocation, terminal/child contest sources, template projection, player
bridge, books, prepared capture, filled CSV, accepted evidence, manifests,
acceptance receipts/root, final-field evidence, raw standings, and normalized
standings are reopened at exact generations. Provider creation time must be no
later than the relevant pre-lock freeze/acceptance boundary; post-lock evidence
must be created after lock and before settlement freeze. URI substrings are not
used to classify content.

### Exact A5 facts and root

The module hard-pins the four IDs, names, fees, capacities, limits, K values,
draft group `151307`, slate `dk-151307`, lock, qualifier/guarantee facts,
template IDs, and ticket destinations. It also hard-pins the exact September 4
terminal source manifest and four child identities.

All facts present in contest-detail are rederived from those bytes. Template
IDs are explicitly attributed to the earlier public-lobby projection and its
semantic SHA, because contest-detail does not carry them. A generation-pinned
raw projection was not found and is not fabricated.

The final allocation must be built from exact source, player-bridge, and four
book bytes, published create-once, independently reopened, then pinned by both
raw identity and semantic SHA. Those live constants remain `None`, and
`live_capture_pins()` fails closed until the real object exists.

### Books and player bridge

Book rows are parsed from exact bytes, never paired with independent inline
rows. The bridge exact-reopens a paid salary catalog, recomputes the production
catalog SHA, and proves complete one-to-one canonical-internal/stable-DK/
draftable/display identity with salary, position, team, active state, slate,
and draft group. Validation replays ordered NFL Classic slots, team limit, and
the $50,000 cap and requires:

```text
roster_sha256 = SHA-256(canonical sorted internal-player membership)
lineup_id = lineup-v1-<roster_sha256>
```

The four paid/shadow allocation edge sets are reconstructed from those exact
books.

### Raw acceptance evidence

Acceptance exactly reopens production `paid-entry-capture/v1`, the exact filled
CSV whose raw SHA/length it records, and canonical accepted-entry evidence.
The receipt's accepted rows and projection SHA are derived from the raw
evidence. A fabricated receipt projection cannot borrow an honest evidence
identity.

### Complete-field settlement

Final-field evidence derives exact contest/draft group, settled state,
displayed final submitted field size, and capture time from a separately exact
provider-source object and binds the raw standings identity. The normalized
artifact derives row count, Entry IDs, competition ranks, signed scores, cash,
tickets, settled time remaining, and bridge-resolved final rosters from those
exact bytes. Displayed and parsed counts must agree.

Settlement reopens the four-contest root, exact contest manifest/acceptance,
normalized field, final-size evidence, raw CSV, and player bridge. It rejects a
truncated file paired with genuine displayed size, another contest's field,
and accepted-to-final roster drift without a separately frozen late-swap
transition. Guaranteed underfill and payout tiers derive from contest-detail.
Cash and ticket awards reconcile separately; tie cash uses exact cent pooling
and deterministic floor/remainder arithmetic with no field-sized tolerance.
Negative fantasy scores remain representable.

## Exact source evidence inspected

The supplied outcome-blind local copies matched the published identities:

| Object | Generation | Bytes | SHA-256 |
|---|---:|---:|---|
| terminal manifest | `1788519340044066` | 2,664 | `28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4` |
| contest `193028206` | `1788519338008617` | 9,220 | `fc90746752ca351b5aaace7f8355327d3d425c09ef1235fbe649fc3c47087bfa` |
| contest `193028208` | `1788519338593279` | 7,784 | `5349b02fde739fbefb0e0eee0000072d8780e5202692eddf6de8cd71822f6602` |
| contest `194478065` | `1788519339081128` | 5,137 | `5126b875ea4ba8dcc323498cd4c644d6eb499315428802197c49f6505349b5ac` |
| contest `194478066` | `1788519339562982` | 4,901 | `ef081a6b0941eedbe539c232d8683babcbe43e5a560aea7861cba5db9738e1ab` |

No outcomes, scores, standings, paid entries, or cloud state were opened. Raw
provider payloads are not committed; exact identities and strict parsers are.

## Validation status

- Python compilation: pass.
- `git diff --check`: pass.
- Five exact source file SHA-256/byte checks: pass.
- Focused repaired v3 pytest: **28/28 passed** in 15.22 seconds.
- Unchanged legacy v2 compatibility pytest: **15/15 passed** in 1.02 seconds.

The authorized serial-lane command record is:

1. `python3 -m pytest -q tests/test_week1_a5_capture_contracts.py` stopped
   before collection because system Python had no `pytest` module.
2. `/home/erich/projects/nfl-predictions/.venv/bin/python -m pytest -q
   tests/test_week1_a5_capture_contracts.py` stopped during collection because
   that venv's editable import pointed at the production checkout. No test item
   ran in either environment miss.
3. With this isolated worktree's `src` explicitly first on `PYTHONPATH`, the
   first focused execution reached the synthetic cohort: 2 independent tests
   passed and 26 setup-dependent cases errored on one qualifier-ticket fixture
   total bug. A one-test diagnostic reproduced that setup error. The parser's
   total now counts source ticket value rather than its deliberately zero cash
   component.
4. `PYTHONPATH=/home/erich/projects/nfl-predictions-week1-capture-v3-p0-repair-20260908/src
   /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest -q
   tests/test_week1_a5_capture_contracts.py` then passed 28/28.
5. The same interpreter/PYTHONPATH command against
   `tests/test_contest_capture_rehearsal.py` passed the unchanged v2 suite
   15/15.

The lane was released immediately after the v2 terminal result. No broad test,
cloud call, provider call, DraftKings action, paid action, or outcome read ran.
Final candidate commit/tree are recorded at handoff after the static closeout.

## Remaining operational blockers

1. The lobby projection has a recorded semantic hash but no generation-pinned
   raw object. Publish/reopen the existing projection bytes without inventing
   or changing their semantics.
2. Final P_MIX/P_CTRL/D400_DEMAX/D800_WEMAX books, exact player bridge, and the
   resulting allocation raw/semantic identity do not yet exist. The live pin
   is intentionally absent.
3. A governed, default-off repository publisher/CLI still must own the entire
   create-once/reopen/receipt sequence; manual JSON is not accepted.
4. Required outcome-blind real-shape smoke, realistic 832,342-row scale
   rehearsal, and independent review remain release gates.
5. Upload/acceptance evidence requires the later owner-authorized paid action;
   settlement evidence necessarily requires post-contest complete exports.
6. Same-field shadow grading and explicit late-swap-transition successors
   remain separately visible P1 work; this repair does not claim them.

Until all pre-entry blockers close, the safe state remains **HOLD before any
A5 manifest publication or paid upload**.
