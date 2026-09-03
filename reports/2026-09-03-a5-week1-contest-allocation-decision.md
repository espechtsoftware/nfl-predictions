# A5 Week-1 contest-allocation decision

Date: 2026-09-03

Status: operator decision; freeze the allocation counts now and bind exact DraftKings contest identities in the
pre-lock Week-1 manifest

## Decision

The operator confirms the allocation previously selected with production:

| Contest class | Planned field | Entry limit/context | Entries | Fee | Planned spend |
|---|---:|---:|---:|---:|---:|
| $5 Millionaire contest | approximately 832,000 | large-field Milly | 57 | $5 | $285 |
| $3 large-field contest | approximately 158,000 | 20-entry maximum | 20 | $3 | $60 |
| Championship qualifier | approximately 5,000 | $18 qualifier | 3 | $18 | $54 |
| Championship qualifier | bind from live manifest | $5 qualifier | 10 | $5 | $50 |
| **Total** | — | — | **90** | — | **$449** |

This decision supersedes the generic Option A/B/C choice in the lab's
`reports/2026-09-02-a5-contest-allocation-options.md`. It deliberately places most entries and spend in contests
that pay cash while retaining bounded championship-qualifier exposure.

## Frozen lineup-to-contest mapping rule

Use nested prefixes of the final ranked entered book:

- ranks 1–57: $5 Milly;
- ranks 1–20: $3 20-entry-max contest;
- ranks 1–3: $18 championship qualifier;
- ranks 1–10: $5 championship qualifier.

The same lineup may therefore enter more than one contest. This is deliberate: the strongest available prefix
receives every scarce qualifier entry instead of assigning lower-ranked lineups merely to force 90 distinct
rosters. The entered manifest must record each `(contest_id, entry_index, lineup_rank, roster_sha256)` edge so the
overlap and self-competition are explicit.

## Week-1 manifest requirements

Before any entry upload and before the applicable contest lock, bind:

1. exact contest ID and contest name for all four classes;
2. observed entry fee, maximum entries, field cap, prize table, ticket terms, and lock time;
3. the final entered-book identity and ordered roster hashes;
4. the four exact K values above and the nested-prefix mapping;
5. an immutable upload artifact plus the accepted-entry receipt;
6. predeclared D400 and same-pool D800_WEMAX shadow books graded at K57/K20/K3/K10 against the same captured
   contest fields;
7. full standings and payout capture inside the approximately four-day DraftKings availability window.

If a named contest is unavailable or its fee/field/entry limit materially differs, do not silently substitute it.
Record the mismatch and put the closest replacement to the operator before entry. A field filling below its cap is
not a material mismatch if the contest identity and prize table are unchanged; record both cap and final field.

## Scope

This freezes contest allocation, not the generator. The current planned Week-1 generator remains the final
operator-approved production package at lock, presently D800_DEMAX subject to the already-declared pre-lock
revision process. This decision does not promote an historical arm, authorize an outcome read, or claim that the
allocation is positive expected value. Its purpose is to align the paid portfolio with the operator's appetite and
make prospective settlement interpretable.
