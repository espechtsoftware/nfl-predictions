# CBWU volume-OI prospective shadow — grading spec (FROZEN before first collection)

**Shadow id:** `2026-cbwu-volume-v1` (queue B1). Frozen 2026-08-19,
BEFORE any 2026 slate is collected. This document is the entire
adoption bar; nothing else licenses a production change.

## What it tests

B2-prime measured retrospectively that admitting more independent seed
books at the FIXED candidate budget raises the selected book
monotonically (mean S 178.38 at five books → 181.13 at fifty-one, tails
12/4/3 → 14/5/4 at 194/210/220). That result read a dose curve against
outcomes on the same 54 slates, so it cannot license adoption. This
shadow re-asks it prospectively on weeks nobody has seen.

## Mechanism (implemented, tested)

Weekly, pre-lock, paired on identical worlds:

- **Control:** the adopted production CBWU combine on the five
  registered seed books — byte-identical to the money path.
- **Treatment:** `combine_cbwu_volume_books` over TWENTY registered seed
  books (the five production pairs plus fifteen frozen pairs from
  `default_rng(20260819)`), admitted at the SAME registered R0 candidate
  budget and scored on the SAME registered R0–R4 world blocks.

Only the candidate-book count changes. At k=5 the combine is provably
identical to the frozen CBWU-OI admission (unit-tested), so any
difference observed is volume and nothing else. Order-invariant by
construction. `production_enabled=False` and
`uses_realized_outcomes=False` are pinned in every receipt.

## Grading (frozen)

- **Population:** every 2026 regular-season Sunday-main slate from Week
  1 through the grading date. No slate may be dropped after the fact.
- **Primary:** paired weekly maximum of the realized book score,
  treatment minus control, reported with
  `research.paired_max_stats.paired_weekly_max_report` (exact sign-flip
  enumeration where feasible, else the fixed-seed MC; Wilcoxon signed
  rank; McNemar at the 187/194/200/210/220 grid).
- **Secondary (reported, non-gating):** selected-book mean, candidate
  union size, admitted-book source counts, and the winner-overlap
  instrument once 2026 winners are known.
- **First grading date:** after **six** graded slates (≈Week 6). One
  interim look at four slates is permitted for SAFETY only — a
  treatment that is materially worse may be stopped early; it may never
  be adopted early.
- **Adoption bar:** paired mean ΔS > 0 with two-sided p ≤ 0.05 on the
  primary AND no threshold-grid regression at 194 or above. Anything
  else means continue collecting or stop; a null does not adopt.
- **Stopping:** if the bar is met, adoption is a separate operator
  decision that changes `multiseed_portfolio` on the money path — the
  shadow itself never writes production lineups.

## Operational

Job `shadow-cbwu-volume`, 16Gi / 4 CPU, 4h task timeout (it builds four
times the books of the incumbent shadow), scheduled Sundays 08:30 CT —
earliest of the Sunday shadows so it completes before the money path's
decision boundary. A failed or late shadow run NEVER blocks the money
book; it simply loses that week from the graded population, which must
be disclosed at grading.
