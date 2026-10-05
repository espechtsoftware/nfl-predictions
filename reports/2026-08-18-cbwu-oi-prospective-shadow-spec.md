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

## Pre-season allocation clarification (2026-08-30)

Before any 2026 regular-season outcome or valid weekly panel existed, the
money generator moved from the 160-leverage/40-boom allocation to boom-first
40/160. This older prospective comparison retained its original 160/40
population so its only treatment difference remains the CBWU combination law;
it does not silently inherit later money-generator changes. Commit `def26c98`
implemented that boundary through `incumbent_control_environment` for both
the captured population and control selector. The phrases "adopted money
environment" above therefore refer to the environment frozen for this shadow,
not to later production allocations. This clarification changes no grading
threshold, membership size, selector, outcome boundary, or production path.

## Rider: Week 1 live entry of the OI top-20 (operator decision, 2026-08-18)

After this spec was frozen, the operator raised the Week 1 entry budget to
100 and allocated seats 81-100 to this shadow's frozen treatment
20-membership, entered live alongside the byte-identical 80-entry money
book. This rider changes NOTHING about collection or grading: the books are
frozen pre-lock regardless of entry, the money path and its 80-license are
untouched, and the preregistered gate stands exactly as written above. The
only new artifact is an entry-export step that reads the already-frozen
20-membership (canonical DK draftable ids) into the DK upload. Live results
of the entered 20 are settlement facts, not grading inputs; the shadow is
graded on the frozen books alone.

## Amendment 1 (2026-10-04): the shadow moves to the current money-path policy from Week 5; the frozen 160/40 comparison ends

Recorded before any Week-5 outcome exists (the Week-5 Sunday main locks 2026-10-11).

**Operator decision (2026-10-04), verbatim:** "we absolutely can change things mid-season because if we don't get
things working in the next week or two, there's going to be not another week."

**1. The frozen 160/40 comparison ends and is not adjudicated.** Collection under this spec's 160-leverage / 40-boom
population (contract `2026-cbwu-oi-v1`, settings sha256
`6d68946b27ca35ace348e7ce08340b22566d806a7caebc3815ea0f989feb425e`) stops after Week 4. No verdict, pass or fail, will
be read from it.
- **Week 1: one valid panel**, `prospective-cbwu-oi-2026w01-20260906T162624Z`, frozen 09-06 before lock and without
  outcomes. The slate check (2026-10-04) PASSED:
  - its draft group 151307 is the Week-1 Sunday main slate (13:00–16:25 ET, 24 teams), the group the fixed
    Sunday-main rule selects;
  - its universe of 398 players, 249 candidate players and 172 selected players all come from that group;
  - none comes from the Wednesday (NE, SEA), Thursday (SF, LA), Monday (DEN, KC) or Sunday-night (DAL, NYG) teams.
- **Weeks 2–4 are lost.** Every scheduled run failed: the job was pinned to the 09-06 image (`918f5574`), which
  predates `193e1b44`. On Sundays after a Thursday game it read the stale full-week draft group and stopped at the
  inference-row guard (OPEN-DEFECTS O-27).
- **Records.** The frozen settings remain in code and may be used only for labelled dry runs and replays. A live panel
  under them is refused from 2026 Week 5.

**2. Companion v1 from Week 5.** From 2026 Week 5 the shadow runs under
`CBWU_OI_CONTRACT=2026-cbwu-oi-companion-v1`.
- **Generation and selection:** the adopted money path's, derived from `ClassicProductionPolicy.engine_environment()`:
  - boom-first role 12 / leverage 40 / boom 160, generation budget 172, CE 0;
  - served position scales;
  - the registered seeds R0–R4 at 10,000 worlds per block, entry basis 80;
  - SELECT_LSE 0, 80 entries, tail line 194.
- **The only difference between arms:** the treatment combines the five identical books with the CBWU-OI-v1 complete
  union; the control uses the money path's CBWU combine.
- **Settings sha256:** `9849d07f0ff22a57f75d10a1e4dc909647ca86563eadc134ed6eaf2d5eff4081`.
- **Enforcement.** The runner refuses a job that does not declare and carry exactly this set.
- **Future changes.** If production_policy changes any of these settings, the published sha changes and the change is
  recorded in a dated amendment before the first affected week.

**3. How it is read.** Each scored companion week is read under the in-season adoption track v2
(`reports/2026-09-19-in-season-adoption-track.md`). Any adoption is the operator's reversible-trial decision, and a
trial's package needs graded companion weeks as its evidence.
- **Pooling.** Companion weeks are never pooled with the 160/40 panel. They carry their own panel prefix
  (`companion-cbwu-oi-v1-`) and run type (`companion_cbwu_oi_v1_shadow`).
- **Non-transfer.** The money path runs boom-first 40/160; under the post-selection law, the frozen 160/40 verdict
  does not transfer to it. A verdict about the policy we run therefore comes only from the companion. Any further
  companion — a different population, law, or downstream stage such as the lab union or head layout — is a NEW
  companion with its own preregistration and compute decision, not an amendment.

**4. Dry runs are never canonical.** A panel with the `dryrun-` prefix, under `recourse_worlds/dryrun/`, or with a
`*_dryrun` run type is never canonical and never read. A companion week's canonical panel is the earliest successfully
frozen panel named `companion-cbwu-oi-v1-{season}w{WW}-*` under `recourse_worlds/{season}/week-{WW}/`. A missed week is
missing: it is not imputed, and no replay substitutes for it.

**5. Ownership records.** Paired and tail shadows no longer append to `nfl_predictions.own_shadow` (O-27; the reviewer
2026-10-04). The table gains a writer column so that any future reader selects by writer.
