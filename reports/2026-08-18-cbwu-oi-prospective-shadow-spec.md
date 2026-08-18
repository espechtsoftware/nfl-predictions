# Frozen spec: CBWU-OI prospective 2026 shadow

Date: 2026-08-18. Frozen BEFORE first collection; no 2026 outcome exists.
Shadow ID: `2026-cbwu-oi-v1`. Operator approval: 2026-08-18 ("wire and
enable now" — this scheduler alone enabled; the rest of the fleet stays
paused).

## Why this shadow exists

CBWU-OI (`combine_cbwu_order_invariant_books`, frozen CBWU-OI-v1) is the
only mechanism that has ever improved retrospective candidate `C` at exactly
equal budget (+5.66 mean, `>=194/200/210` 11/8/6 -> 18/14/10 on the 54-slate
corpus, 2026-08-16). Its promotion requires prospective evidence, and by the
2026-08-18 power analysis it is the only known member of the class of
effects large enough for a low-power realized gate. Until today no
collection vehicle existed (the 2026-08-18 briefing review's §C finding).

## Collection (outcome-blind)

Every 2026 regular-season Sunday-main week, job `shadow-cbwu-oi-paired`
(schedulers `s-shadow-cbwu-oi-paired-early/late`, Sundays 09:45/10:45 UTC;
the late run overwrites nothing — each run freezes a new immutable
`prospective-cbwu-oi-*` panel id):

- Runs the complete adopted money environment with exactly one change:
  `MULTISEED_PORTFOLIO=CBWU_OI_SHADOW`
  (`production_policy.cbwu_oi_shadow_environment`).
- Builds the five R0-R4 books once from the live snapshot, then both
  combines on the identical books: control = adopted `combine_cbwu_books`,
  treatment = frozen CBWU-OI-v1 union. `paired_shadow_receipt` enforces
  identical player worlds, identical budgets, and freezes exact 20/40/80
  DK-roster memberships for both arms pre-lock, plus both candidate
  batches as immutable recourse artifacts (create-only GCS).
- Reads no outcome. `production_enabled=false` everywhere; money lineups
  are untouched.

Pre-season scheduler firings (before DK posts a Sunday-main draft group)
fail on the empty-slate guard; that is expected noise, accepted in exchange
for not having to remember a flip at Week 1 (the `dk_contest_fills`
precedent).

## Grading (preregistered, before any outcome was seen)

Grade once after the 2026 regular season; an interim descriptive read is
permitted at >=12 collected weeks but licenses nothing. For each collected
week, score both frozen 80-entry memberships on realized DK points and take
each arm's weekly maximum, using the canonical earliest successfully frozen
panel per week.

**Primary preregistered gate — all three must hold:**

1. **Discordant pairs at 194** (the 2026-08-18 review's statistic): weeks
   where treatment clears 194 and control does not must strictly exceed
   weeks where control clears and treatment does not.
2. Paired mean weekly-max delta (treatment minus control) `>= 0`.
3. No decline in weeks with maxima `>= 210`.

Context, explicitly non-gating: full discordant tables at
187/200/210/220/230/240, per-size (20/40) memberships, candidate overlap/
union trajectories, and distinct weeks moved.

**Consequences.** Passing licenses a promotion *proposal* to the operator —
not automatic adoption. Failing closes CBWU-OI promotion on 2026 evidence;
no threshold, week-subset, or membership-size re-selection may rescue it.
No mid-season refit, re-selection, or bar change is permitted; a bar change
after any outcome is visible voids the shadow.

## Bindings

- Portfolio dispatch: `live_lineups.py` `CBWU_OI_SHADOW` branch (paired
  control capture + OI union on identical books).
- Runner: `prospective_shadow.run_paired_prospective_shadow(variant="cbwu_oi")`,
  CLI `shadow-cbwu-oi-paired`.
- The `SELECT_LSE="0"` unchanged selector on both arms, tail line 194.0,
  80 entries, identical seeds R0-R4 — all inherited unchanged from the
  adopted money policy.
