# Laptop review item 7: the tolerances were absorbing our own granularity error

Answering item 7 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Standings validator: reconcile tie rows, entry counts, duplicate exports and rounded
> ownership summaries before widening tolerance. Preserve raw hashes and import
> rejected-row evidence. Never silently alter roster or FPTS reconciliation.

**You were right to stop the widening, and the reason is worse than "premature".** The
tolerances were not absorbing DraftKings error. They were absorbing a mismatch between
the granularity DK writes and the granularity we compared at — which meant the check
could not fail closed on a genuine contradiction. I have reconciled all twelve settled
Week-2 exports, replaced the tolerance with an exact test, and **empirically confirmed
that the old path accepted a tripled ownership share.**

## 1. What DK actually writes

DK's `%Drafted` summary is keyed by **(player, roster position)** — a player used at RB
in some lineups and FLEX in others gets two rows — and it **omits rows held by very few
entries**. We compared per *player*, summing those rows. So a dropped FLEX row looked
exactly like DK disagreeing with us about that player's share, and each time it appeared
the response was a wider allowance:

- 2026-09-14: "short by one or two entries' worth on a player below 1%" → tolerated
- 2026-09-21: `gap <= 2.0 * one_entry + 0.011`, and a second branch tolerating a **60%
  relative error** (`gap <= 0.6 * ours`) on any player under 2%
- 2026-09-21: summed-mass tolerance widened from a flat 2.0 to `min(10.0, max(2.0, 600/field))`

## 2. The reconciliation, on all twelve exports

Ground truth is the lineup column of the same file — nothing external.

| | result |
|---|---|
| lineups with a slot count other than 9 | **0 of 12 contests** (`slot_gap = 0` everywhere) |
| (player, slot) rows DK lists that no lineup uses | **0** |
| **max deviation of any listed share from the lineups** | **≤ 0.005 in every contest** |
| summed-mass gap explained by omitted rows | **all of it** |

**0.005 is exactly half of DK's two-decimal printing unit.** Every listed share is
correct to the last digit DK prints. *There are no real per-player mismatches anywhere in
the corpus.* Every tolerance existed for omitted rows.

The three contests that had breached the flat 2.0 mass tolerance:

| contest | field | mass gap | omitted rows | their mass | residual |
|---|---:|---:|---:|---:|---:|
| satellite | 68 | 4.57 | 3 | 4.412 | **0.158** |
| ffwc qualifier | 59 | 5.48 | 2 | 5.085 | **0.395** |
| supersat 1b | 594 | 1.42 | 7 | 1.684 | **-0.264** |

In a 68-entry field one roster slot is worth 1.47 points of mass, so DK dropping three
low-exposure rows blows past a flat 2.0 with nothing wrong at all.

*(My first pass reported 23 "missing" DSTs in the 68-entry contest. That was my scratch
parser, not DK: the export writes DST team names with a trailing space. Production
already strips it. Recorded because it is exactly the kind of artifact that gets
mistaken for a data defect and answered with a wider tolerance.)*

## 3. The fix

`_reconcile_ownership_by_slot()` compares at DK's own granularity and prices the gap
instead of tolerating it:

- every **listed** (player, slot) share must be within 0.005 of the lineup-derived value — otherwise `ownership_mismatch`, fail closed
- a share claimed for a slot **no lineup used** fails closed
- a **repeated** (player, slot) row fails closed (a duplicated summary block would otherwise inflate the mass and still reconcile)
- **omitted** rows are counted, priced, and receipted — DK's truncation is not our error, but it is no longer invisible
- the residual after crediting omissions must fit the printing budget (`0.005 x listed rows`)

The receipt gains `slot_reconciliation`: rows listed, rows omitted, omitted mass,
residual, budget, max listed deviation, and the largest omitted keys by name.
`ownership_mass_tolerance` is replaced by `ownership_mass_residual`.

All twelve exports pass, with `max_listed_deviation` between 0.00471 and 0.00500 — right
at the printing bound and never above it.

## 4. Proof the old check was actually unsafe

Not an argument — a run. A synthetic export where DK claims Swing Man at **3%** of a
100-entry field while the lineups put him at **1%**: a tripled share, inside the old
allowance (gap 2.0 ≤ 2 × one entry) and inside the old mass tolerance of 6.0.

```
with the new check active:
  FAILED (ownership_mismatch) <- correct
with the new check neutered (i.e. the pre-2026-09-22 behaviour):
  PASSED  <-- confirms the old path tolerated a tripled share
```

It did not merely pass — it logged the tripled share as a *tolerated low-owned player*.
That case is now `test_a_contradicted_share_the_old_tolerance_allowed_now_fails_closed`.

## 5. The rest of item 7

- **Tie rows: already correct, and heavily exercised.** Competition rank is reproduced
  from points rounded to DK's precision. Ties are not an edge case here — in the
  Millionaire **100% of entries share a score with another entry** (172,761 entries,
  6,812 distinct ranks). All twelve reproduce.
- **Entry counts: reconcile exactly.** Blank-lineup entries are counted into the field
  and excluded from the roster frame; `slots = 9 x filled` in all twelve.
- **Duplicate exports:** duplicate `EntryId`s already fail closed, and a repeated
  (player, slot) row now does too.
- **Raw hashes: preserved** — `source_sha256`, `source_bytes`, `source_filename` on every
  capture; rejected-row evidence goes to `--failure-manifest`.
- **Roster/FPTS reconciliation unchanged.** The lineups remain the authority; nothing in
  this change alters a roster or an FPTS value.

## 6. Three existing tests changed, deliberately

They encoded the old diagnosis, so I am flagging rather than burying them:

| test | change |
|---|---|
| `test_validation_reconstructs_ownership_from_entry_rosters` | still fails closed; now asserts the offending key is **named** (`Wrong Player/QB`) |
| `test_mass_tolerance_scales_with_the_field` | renamed to `test_the_summed_mass_gap_is_priced_against_the_lineups_not_tolerated`; asserts a **zero residual** instead of a tolerance value |
| `test_validation_failures_carry_a_typed_result_class` | a listed row carrying a wrong number is reclassified `entries_complete_ownership_incomplete` → **`ownership_mismatch`**; a new out-of-range case covers the old class |

That reclassification is a real semantic change: "incomplete" is now reserved for a
summary that is structurally unusable. Nothing outside the module branches on the class
(checked), so it is contained.

## 7. Recommended, not done

`_validate_ownership_against_entries` still carries its per-player tolerances, including
the 60%-relative-error branch. They are now **dead weight**: the slot check is strictly
tighter, so nothing can reach them that the slot check has not already accepted. I left
them because removing them means rewriting two more tests
(`test_small_field_one_entry_shortfall_...`, `test_large_field_half_share_...`) that pin
the old diagnosis as intended behaviour, and that is a decision worth making with you
rather than on my own before Week 3. **Recommendation: delete both branches after Week 3
capture.**

Reproduce: `reports/item7-standings-reconciliation/reconcile.py` and
`ownership_reconciliation.csv` (aggregates only — the raw exports stay under
`/home/erich/week2-sunday/ENTERED/` and are never committed).
