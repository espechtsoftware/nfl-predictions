# Preregistration: prospective tail-supply shadow arms, 2026 season

**Registered:** 2026-09-12, before any 2026 regular-season outcome exists
(Week-1 lock 2026-09-13T17:00Z). **Source:** state audit §5.2 ("Supply at
220+ — the only path to the stated goal"). **Scope:** gates and KPIs only. No
arm is implemented, no image is built, no allocation changes. Everything below
is frozen so that the weekly reads are prospective grading, not panel mining.

## Why this exists

The realized-score work of 2026-09-12 split the tail in two: below ~210 the
binding constraint is retrieval (the pool holds the clears; the book misses
them; more entries is the proven lever), above ~220 it is supply (the pool
holds a 230+ candidate in 1 of 72 slates; no selector or entry count can
retrieve what was never generated). Every historical panel is now an opened
outcome for this program, so a tail-supply mechanism can only be judged on
2026 weeks, with the rule fixed before the weeks are played.

## Arms (prospective shadow arms in the weekly generation-shadow family)

All arms run at the same core-solve budget as the control unless stated, use
the untouched shared base-law simulation/selection banks, and are registered
with `status: exploratory`, `decision_role: diagnostic-only`,
`required_before_week1: false`, `primary_efficacy_rule_satisfaction_allowed:
false`. None can satisfy the registry's primary efficacy rule; adoption is a
separate protocol.

| id (proposed) | mechanism | why it is here |
|---|---|---|
| `direct-tail-083-v1` | direct-tail generation (the 083 mechanism) as a generator arm | the only arm whose supply ratio rose with threshold; its read failed at selection, not supply |
| `belief-gated-completion-v1` | belief-gated / minimal-core completion | 3× the 220+ supply at zero mean cost in its read; the gate was sited on the mean |
| `column-pricing-m1-v1` | one column-generation pricing pass: build the book, price worlds where it is weak on a held-out bank, solve for maximum positive reduced value, add | never tried; the first mechanism that lets selection tell generation what it is missing |
| `scenario-reduction-s1-v1` | scenario reduction for solve worlds, co-run against total-order scheduling at equal budget | attacks the ~31-effective-rank redundancy at the source |

**Control:** `boom-first-40-160` (the money-path generator), same slate, same
banks. **Reference:** `incumbent-160-40`.

## Weekly measurements (per arm, per slate; all from the tail ledger row)

Primary, gated:

- `S200`, `S210`: count of the arm's supplied candidates with realized score
  ≥ 200 and ≥ 210.
- `POOLMAX`: the arm's realized pool maximum.

Secondary, reported, never gated:

- `S220`, `S230`: counts at ≥ 220 and ≥ 230.
- Base-law retrieval at K20/K40/K80: how many of the arm's 210+ / 220+
  candidates survive the untouched base selector (does new supply survive
  selection?).
- Mean supplied score (mean cost of the mechanism).

Ledger identity: every read cites the ledger row's `row_sha256` and input
identities; a row produced with JSON-mode actuals is not a read.

## Decision rules (frozen)

Let `d_w = S200(arm) − S200(control)` on week `w`, and likewise for `S210`
and `POOLMAX`.

1. **Interim (after 8 graded weeks, matching the registry's
   `INTERIM_WEEK_COUNT`).** An arm is *promising* if all hold:
   `d_w ≥ 0` for S200 in ≥ 5 of 8 weeks; `POOLMAX(arm) ≥ POOLMAX(control)` in
   ≥ 5 of 8 weeks; mean `S210(arm)` ≥ mean `S210(control)`. Otherwise it is
   *not promising* and is closed for the season if `d_w < 0` for S200 in ≥ 5
   of 8 weeks.
2. **Full season (18 weeks).** One-sided sign test on `d_w` for S200 at
   α = 0.05, plus the registry's predeclared non-inferiority tail guard over
   the complete threshold surface (an arm that raises 200+ supply by lowering
   194 coverage fails). Both must hold to be *supported*.
3. **220+/230+ are never a pass.** A 230+ candidate the control did not
   supply is recorded as discovery evidence for that mechanism only. With
   ~17 slates and a ~5% base rate no arm reaches significance at 220 in one
   season; claiming it would be the panel-mining error this document exists
   to prevent.
4. **Supported ≠ adopted.** A supported arm enters the existing registry
   promotion path as a challenger with its own frozen primary rule; the
   sleeve below is the only pre-registered live exposure and requires an
   operator decision.

## Preflight rule for the belief gate

`belief-gated-completion-v1` sites its gate on the 220+ supply *count*.
Before that gate is frozen, run an outcome-blind support census on the 2026
shadow artifacts: identity, eligibility and count of candidates per week that
the gate could admit. If the required support is absent, redesign the gate
before freezing rather than weakening the eligibility rule after a treatment
grid has been observed (CLAUDE.md preflight rule).

## Sleeve (second-stage, operator decision)

If `direct-tail-083-v1` is *promising* at the interim read, a fixed-size
sleeve of 8 of the 57 unique Millionaire slots may admit its candidates to the
paid book. Measured by the ledger's book tail counts and by the realized score
of the 8 admitted lineups against the 8 lineups they displaced (both recorded
in the publisher's participation map). The 088 "sleeves are null/harmful"
result was about retention from the same pool; this sleeve carries new
candidates, which is why it is not already closed.

## Exclusions

- No historical panel read for any of these arms (2019–2025 panels are opened
  outcomes for this program).
- No selector tuning on 2026 outcomes; the base law stays untouched.
- No arm may be added to the paid book outside the sleeve rule above.
- A missed week (arm not executed before lock) is a missing observation, not
  a zero; the week counts stay as graded weeks only.

## Implementation notes (not part of the freeze)

Arms are added to `prospective_generation_shadow_registry.py`, need an image
rebuild and the create-once weekly suite execution
(`scripts/cloud_generation_shadow_suite.sh`), and each must pass one
outcome-blind smoke against real Week-N pre-lock artifacts before its first
graded week. First possible graded week is the week after an arm's smoke
passes; the FP/SIS ablation stays parked (audit §5.4).
