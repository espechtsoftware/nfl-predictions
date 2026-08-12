# Review: PIT repair, team-QB feature, and fitted-K rejection

Date: 2026-08-12. Review of the work through commit `24c742a`, focused on
necessary changes. **No code was changed.**

---

## Verified correct

Stated first because the repair work is strong and two of the findings are ones
my earlier audit did not reach.

- **The injury post-lock leak is a material find I missed.** 24 deterministic
  latest revisions land after the common Sunday-main lock, four of them `Out`.
  Post-lock knowledge that a player is out is directly outcome-bearing, and it
  sat in an active feature table. The `slate_locks` definition —
  `MIN` kickoff over Sunday `REG` games with `13:00 <= gametime < 19:00` ET —
  correctly reproduces the same common-lock semantics established by the
  earlier `market_points()` correction.
- **The smoother position-prior defect was worse than I estimated.** I flagged
  `position` as a leaked feature affecting ~1% of player-seasons; the actual
  exposure included `rz20_targets_smoothed` and `gl3_carries_smoothed` borrowing
  across seasons, changing 3,625 / 3,640 rows at maximum absolute deltas
  `0.0673` / `0.0572`.
- **Marking the v1 active-label exact-80 pre-launch invalid** rather than
  salvaging it is the right call, and the unchanged-law repair path
  (rebuild → reconcile → retrain → write-once v2 caches → repeat the identical
  score-free gate) preserves the comparison's meaning.
- **The observer-blinding deviation was handled correctly** — disclosed, scoped
  to three slates, no decision taken from the exposed values, comparator and
  both next-stage launches already frozen. That is the right response to an
  accidental exposure.
- **My Finding 1 is fully closed.** `team_week_pace`, `defense_week_blitz`,
  `team_week_target_concentration` and `team_week_ftn_offense` all now carry
  upcoming-week spines.
- **My Finding 2 was addressed better than I proposed.** Rather than extending
  per-feature window checks, `features/leakage.py` now independently
  reconstructs whole families — 29 usage fields, injury values/timestamps/status,
  and downstream vacated opportunity — with exact key/null/value parity. That
  is a stronger guarantee than the per-column assertions I suggested.
- **`017l_team_qb_quality.sql` is well built.** Strict `6 PRECEDING AND 1
  PRECEDING`, dropback-weighted aggregation (`SUM(cpoe_sum)/SUM(cpoe_dropbacks)`
  rather than a mean of weekly means), completed-games-only spine plus the live
  target row with the reasoning documented, team-abbreviation normalisation,
  `season_type = 'REG'`, an independent Python recomputation check, and held as
  a side table so the repaired cache identity is unchanged.

---

## Recommended changes

Ranked. Nothing blocks the current queue.

### 1. `017l` crosses season boundaries with no indicator — do this before the arm runs

The window is `PARTITION BY team ORDER BY season, week` with
`ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING`. Partitioning by `team` alone means
a Week 1 row's six-game window is **entirely the prior season's team games** —
frequently under a different starting quarterback.

`team_qb_cpoe_games_l6` and `team_qb_cpoe_dropbacks_l6` let the model learn from
support volume, but neither tells it that the support came from a different
season. The project already has exactly this pattern in `fp_route_cross_season`.

**Add `team_qb_cpoe_cross_season`** (or restrict the window to same-season with
an explicit prior-season fallback column). One column, consistent with existing
precedent, and Weeks 1–6 are precisely where a quarterback change makes the
carried value misleading. Doing it after the arm runs would require a new arm.

### 2. `017l` measures team passing efficiency, not QB quality — say so in the protocol

CPOE is completion percentage above expectation, which depends on the thrower
*and* the catcher. A team-level CPOE aggregate broadcast to a receiver therefore
partly feeds that receiver back his own prior contribution.

This is legitimate predictive information — it is the same class as
`target_share_last`, and it is strictly prior — so it is not a defect. But the
name invites over-interpretation, and the frozen protocol should state what the
quantity actually is so a passing result is not read as "QB quality helps
receivers."

The cleaner variant, if this one passes, restricts the aggregate to the team's
primary passer identity using `player_week_role`, which separates thrower skill
from receiving-corps quality. Worth naming now as the designated follow-up
rather than discovering it after a positive result.

### 3. Delete the dead `qb_quality` / `team_cpoe` CTE in `015_player_week_efficiency.sql`

Lines 34–41 define:

```sql
qb_quality AS (
  -- CPOE of the team's primary passer, trailing; a receiver feature.
  SELECT posteam AS team, season, week, AVG(cpoe) AS team_cpoe
  FROM `${raw}.pbp` WHERE qb_dropback = 1 AND cpoe IS NOT NULL
  GROUP BY 1, 2, 3
),
```

`team_cpoe` is never selected — the CTE is evaluated and discarded. That was
harmless when nothing else computed team CPOE. It is no longer harmless: `017l`
now computes the same underlying quantity with **different and more careful
semantics** (dropback-weighted, strictly prior, schedule-spined), while `015`
retains an unused *same-week, unweighted* version.

Two near-identical constructs with different correctness properties in different
files is an active confusion hazard. Delete it, or replace it with a one-line
pointer to `017l`.

### 4. `014` still carries the end-of-season position fallback

`014_player_week_usage.sql:7` retains:

```sql
SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
```

feeding `COALESCE(r.position, pm.position)` at lines 181 and 206. Exposure is now
narrow — fallback-only, firing when the primary position is NULL — but
`017_defense_week_allowed.sql` was repaired to remove exactly this pattern, so
the codebase is now inconsistent about it.

Replace with a strictly-prior resolution (`LAST_VALUE(...) ROWS BETWEEN
UNBOUNDED PRECEDING AND 1 PRECEDING`) plus a preseason-roster fallback for
week 1. Low priority; do it on the next feature rebuild.

`022_defense_points_against.sql:10` also retains the pattern, and that one is
**correct as-is** — it is the documented rear-view UI table and is not a model
input. Worth a comment noting the deliberate difference so a future sweep does
not "fix" it.

### 5. Assert `slate_lock_at` coverage — the only silent-failure mode here

`018_player_week_injury.sql` filters with `i.date_modified <= l.slate_lock_at`.
If any `(season, week)` has no Sunday `REG` game in the 13:00–19:00 ET window,
`slate_lock_at` is NULL, the comparison evaluates FALSE for every row, and
**that week loses its entire injury dataset with no error raised**.

Week 18 flex scheduling is the realistic trigger. A single assertion — every
`(season, week)` in the panel has a non-null `slate_lock_at`, and the injury row
count per week is non-zero — closes it. This is the only item in the review that
can fail silently, so it is worth doing even though the trigger is rare.

Related: the lock is deliberately Sunday-main-only, which is correct for the
classic slate and is documented in the file. If a Showdown, Thursday or Saturday
path is ever added, this reader is wrong for it; an explicit guard against reuse
outside the main-slate context would prevent repeating the `market_points()`
failure mode.

### 6. Make the upcoming-spine guarantee structural rather than instance-by-instance

All four missing spines were repaired individually, and `leakage.py` now
references `ro.is_upcoming` in several places. But nothing generic prevents the
*next* new table from repeating it.

A single standing check — for the current season's maximum scheduled week, every
table joined by `player_week_inference` returns a non-null row for the spine's
upcoming rows — converts a recurring class into a build-time failure. This is
the same shape as the `features.txt` ↔ `NUMERIC_FEATURES` manifest assertion
recommended earlier, and for the same reason.

---

## Note on the fitted-K rejection

The disposition is right and the reasoning in the result document is the
important part: **better held-out conditional allocation likelihood did not
translate into better extreme portfolio scores.** Recording that explicitly —
and noting it is exactly why the score-free mechanism gate and the lineup gate
were separated — is the most valuable sentence produced by that arm.

It is also the third instance of the same pattern (route share improved
MAE/CRPS, fast-role beat matched controls, fitted-K improved allocation
likelihood; all three failed the lineup gate). That pattern is worth carrying
into the end-of-program forensic analysis as a named question rather than three
separate footnotes: **which distributional improvements convert to portfolio
score, and which do not, and why.**

---

## Housekeeping

`HANDOFF.md` states that the ten operator-supplied outside-review documents
"remain untracked and must not be staged or modified." They are now tracked —
`git ls-files` returns them and the working tree is clean. The instruction is
stale and should be updated to reflect their tracked status, or the files
untracked again, so the next session is not working from a false premise about
repository state.
