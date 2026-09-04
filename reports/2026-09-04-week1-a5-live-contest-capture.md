# Week-1 A5 live contest capture

Date: 2026-09-04 UTC

Scope: pre-lock DraftKings lobby facts for the operator-approved A5 allocation

Outcome boundary: no contest outcome, score, ownership, rank, or payout result was read

## Result

The repaired NFL contest collector successfully captured the 2026 Week-1
Sunday-main lobby. The intended four A5 contests all resolve to draft group
`151307` and lock at `2026-09-13T17:00:00Z`.

| A5 use | Contest ID | Live contest name | Fee | Field capacity | Current entries | Per-user limit |
|---|---:|---|---:|---:|---:|---:|
| 57-entry Milly prefix | `193028206` | NFL $3.5M Fantasy Football Millionaire [$1M to 1st] | $5 | 832,342 | 207,098 | 150 |
| 20-entry secondary prefix | `193028208` | NFL $400K Play-Action [20 Entry Max] | $3 | 158,541 | 19,086 | 20 |
| 3-entry $18 qualifier prefix | `194478066` | $14M 2026 Fantasy Football World Championship Qualifier #6 | $18 | 5,000 | 769 | 150 |
| 10-entry $5 qualifier prefix | `194478065` | $14M 2026 Fantasy Football World Championship Qualifier #5 | $5 | 17,835 | 1,222 | 150 |

The warehouse values above are the latest rows from the successful capture at
`2026-09-04T02:40:37Z`. Field capacity is the DraftKings lobby field `m`; it
must not be confused with the per-user entry limit `mec`.

The same bounded public-payload inspection observed:

- contest-template IDs `963916` (Milly), `388597` (Play-Action), `970817`
  ($18 qualifier), and `970816` ($5 qualifier);
- `attr.IsQualifier=true` on both qualifiers;
- public payout-description metadata of `1 Contest Seat` plus `$6,500` for
  the $18 qualifier and `1 Contest Seat` plus `$5,000` for the $5 qualifier.

Those public payout descriptions are useful evidence, but they are not a
substitute for the A5 contract's separately required immutable ticket-terms
identity. Contest IDs are therefore identified, while the final A5 package is
not yet sealed.

## Repair and execution evidence

The first current-image execution, `ingest-contests-qts95`, found 2,847 NFL
contests but failed before writing because the destination table is clustered
on `(draft_group_id, contest_id)` and the writer supplied only its partition
field. Production repaired that exact writer boundary in commit
`3473b04a1e296d0db0981c7f648089242d07f61f`.

The scoped build used only a 19.3-MiB allowlisted context:

- Cloud Build: `6a809c64-8f37-48fb-8918-bf722f3834df`
- immutable image digest:
  `sha256:aa31e5c319234139294f25b0ba32bc5cfbe6e41a679c0ec208d238ea282e205e`
- replacement execution: `ingest-contests-c2xf4`
- terminal state: 1/1 success, zero retries
- completion: `2026-09-04T02:40:47Z`
- captured population: 2,847 contests across three upcoming NFL draft groups,
  including 1,719 guaranteed contests

## Follow-on hardening

The collector now preserves the A5-relevant public fields on each future
snapshot: `entry_limit`, `is_qualifier`, `contest_template_id`, and canonical
`payout_metadata_json`. The append path already permits additive schema
evolution. Its scoped release gate now tests both CFB collection and the NFL
contest writer, including compilation, image import, and disabled-command
smokes.

This follow-on schema expansion does not require another immediate endpoint
request. It can enter the next scoped collection image and populate naturally
on the next scheduled poll.

## Exact next steps

1. Capture and bind the complete qualifier ticket terms separately from the
   public payout-summary field.
2. Generate/freeze the Week-1 P_MIX/P_CTRL paid candidates and the predeclared
   D400_DEMAX and D800_WEMAX shadow books at K57/K20/K3/K10.
3. Produce the ordered contest-entry edge manifest, then retain accepted-entry
   receipts and post-contest settlement artifacts under the existing boundary.

## 2026-09-04 10:48Z source-identity completion

Production manually invoked the already deployed, immutable collector after
the additive schema release. Execution `ingest-contests-wwcm2` completed exact
1/1 success with zero retries. It appended a common four-contest snapshot at
`2026-09-04T10:47:54.076774Z` and populated `entry_limit`, `is_qualifier`,
`contest_template_id`, and `payout_metadata_json` for every A5 contest.

The canonical source projection orders rows by string `contest_id`, uses the
fields `pulled_at`, `contest_id`, `draft_group_id`, `name`, `entry_fee`,
`max_entries`, `entry_limit`, `entries`, `is_qualifier`,
`contest_template_id`, `payout_metadata_json`, and `start_time`, then serializes
the resulting JSON array with sorted keys and compact separators. Its SHA-256
is:

`5a98a3ebeb03e0f95afe8845e1f66cf7a21882054f45dd23ef9e85cde60611ee`

This completes the immutable public-lobby metadata identity. It does not
upgrade the two payout-description summaries into complete qualifier ticket
terms; that separate evidence remains required before the final A5 seal.
