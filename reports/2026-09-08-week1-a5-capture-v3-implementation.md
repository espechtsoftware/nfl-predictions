# Week-1 A5 capture-v3 implementation

> **Superseded / P0 HOLD:** independent review found this candidate unsafe for
> manifest publication, paid acceptance, or settlement. The bounded repair and
> current operational blockers are in
> `reports/2026-09-08-week1-a5-capture-v3-p0-repair.md`. Historical statements
> and validation counts below describe only the held original candidate.

Date: 2026-09-08
Branch: `codex/week1-capture-v3-20260908`
Initial implementation base: production `origin/main`
`680c7aa120c5400779d849a13b03f24c2670c720`. The final branch is rebased to
the current production tip before publication; see the final HANDOFF entry for
that exact parent.

## Outcome

A bounded capture successor now represents the frozen A5 allocation without
changing scoring, lineup generation, selection, deployment, or paid-entry
behavior. The implementation preserves `dk-contest-manifest/v2` and adds:

- `dk-contest-manifest/v3` for immutable pre-lock contest facts;
- `week1-a5-entry-acceptance/v1` for exact DraftKings Entry ID, A5 edge,
  roster, prepared-capture, and filled-upload evidence;
- `week1-a5-entry-acceptance-root/v1` requiring all four contests and exactly
  90 paid accepted entries; and
- `dk-contest-settlement/v1` for complete settled field size, ranks, scores,
  payouts, ties, and accepted-entry reconciliation.

The code is
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py`. The operational contract
and exact order are in `docs/week1-a5-capture-contract-v3.md`.

## The repaired field-size boundary

The pre-lock v3 manifest records these as independent facts:

- `advertised_field_capacity`;
- `entries_observed_at_freeze`; and
- the timestamp/source identity for that current-entry observation.

It contains no final field size. Only the post-settlement artifact records
`observed_final_field_size`, after a complete-field confirmation, and binds it
to the exact pre-lock manifest. An underfilled contest therefore leaves both
the advertised capacity and the earlier lobby observation unchanged.

Payout rows are validated against advertised capacity. For the explicit
`prelock-applicable-ranks-only` underfill policy, settlement reconciles only
the occupied ranks `1..observed_final_field_size`, including tie splits. An
underfilled contest that declares `official-settlement-ladder` fails closed in
v1 until a separately sourced final-ladder successor is implemented; it never
silently rewrites the pre-lock ladder.

## Frozen A5 identity enforced

The contract reopens and validates `week1-a5-contest-allocation/v1`, including
the exact owner-approved mapping:

| Role | Contest ID | Paid K | Shadow K |
|---|---:|---:|---:|
| Milly | `193028206` | 57 | 57 × 3 |
| $3 20-max | `193028208` | 20 | 20 × 3 |
| $18 qualifier | `194478066` | 3 | 3 × 3 |
| $5 qualifier | `194478065` | 10 | 10 × 3 |

Every manifest binds the generation-pinned allocation root, its exact
one-contest paid and shadow edge slice, and contest-ready P_MIX, P_CTRL,
D400_DEMAX, and D800_WEMAX books. Book rows include lineup rank/ID, canonical
roster SHA, internal player IDs, and ordered DK draftable IDs. The book must
exactly reproduce the allocation edges at contest K.

The entry-acceptance receipt makes the existing exporter's zero-based fields
explicitly interoperable with the allocation's one-based edges:

```text
a5_entry_index = export_ordinal + 1
a5_lineup_rank = paid_input_book_ordinal + 1
```

The accepted Entry History projection must have exact contest/draft-group
identity, exact K, `accepted` status, unique Entry IDs, and exact ordered slot
IDs. One roster substitution, reordered/missing player, unexpected lineup,
duplicate Entry ID, or missing contest fails the receipt/root.

## Existing durable inputs

The live A5 contest identities remain those frozen under the create-once
contest detail manifest:

- manifest URI:
  `gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/contests/a5/20260904T105535Z/manifest.json`;
- generation: `1788519340044066`;
- bytes: `2664`;
- SHA-256:
  `28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4`.

Its four generation-pinned contest sources and ticket/payout details are
listed in `reports/2026-09-04-week1-a5-live-contest-capture.md`. Those sources
are usable inputs, subject to the required final pre-entry equality/current-
entries refresh. They are not book or accepted-entry evidence.

## Exact operational blockers, ranked

1. **Fresh point-in-time Week-1 inputs are not yet accepted.** The last audit
   found empty Week-1 injury snapshot/feature rows. The repaired injury
   collector must be released, then `ingest-nflverse`, `ingest-dk`, the other
   live feeds, `build-features`, `project-slate`, and `check-freshness` must
   pass serially on one accepted image. The contract does not relax freshness
   or permit an older projection batch.
2. **No governed P_MIX A5 book publisher currently exists.** Production has
   builders/validators, but no accepted single command that generation-
   exactly publishes the P_MIX/P_CTRL K80 pair, D400_DEMAX, D800_WEMAX,
   contest-ready DK player bridges, and final A5 allocation root. The older
   `scripts/publish_week1_operating_book.py` is not this four-policy A5
   publisher. This must be implemented/reviewed or an existing exact operator
   must be identified; unreceipted manual JSON is not acceptable.
3. **The canonical paid-v3 runtime remains held.** As of the implementation
   base, its posttraffic activation identity was still replaceable across
   delete/recreate history. The separate R4 repair/review must pass before any
   paid CSV route is treated as authoritative. Capture v3 does not bypass or
   authorize that path.
4. **No upload or acceptance evidence can exist before the owner performs the
   paid DraftKings action.** After the four exact books/manifests exist, the
   owner uploads K57/K20/K3/K10. Production archives the prepared capture and
   exact CSV bytes, then records Entry History evidence and creates four
   acceptance receipts plus the 90-entry root before lock.
5. **Settlement is necessarily post-contest and perishable.** Download all
   four complete standings files after settlement and before DraftKings
   removes them. Use the displayed final submitted field size—not capacity or
   the earlier current count—for `capture-dk-standings`, then build the
   settlement receipts.

## Safe actions available before paid entry

- independently review this contract and its adversarial test surface;
- deploy/execute the separately reviewed injury repair and restore fresh live
  PIT inputs under normal authorization;
- implement and independently review the missing A5 book/allocation publisher;
- refresh the four contest sources/current-entry observations without
  relabeling the prior immutable snapshot;
- generate the 90 paid plus 270 shadow contest-ready books and four v3
  manifests before lock; and
- prepare an operator directory and browser checklist for immutable filled CSV,
  Entry History, and four standings downloads.

None of those steps requires reading a contest outcome. Only the final paid
upload requires owner authorization; only settlement reads realized results.

## Validation status

Checks completed on the isolated worktree:

- Python compilation: pass;
- Ruff on the new module/test: pass;
- `git diff --check`: pass; and
- successor focused suite: **11/11 pass in 1.93 seconds**; and
- unchanged legacy v2 rehearsal suite: **15/15 pass in 0.99 seconds**.

The first focused pytest invocation exposed only a timestamp-text normalization
error and terminated with 9 failures before the fix. That bug is repaired and
the complete successor suite now passes. After a second exact empty global
pytest census and a separately granted serial window, the unchanged legacy v2
rehearsal module also passed. The lane was released immediately after each
terminal invocation. No broad suite was started or is warranted for this
isolated, default-off contract.
