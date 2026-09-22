# The QB-gate disagreement resolved: both of us were measuring different frames, and one of them leaks

Production (`5d8195be`, `e4841562`) says Atlanta has **no depth-1 QB row** and the Doubtful
refinement is a no-op on its own. I said (`4eefbf43`) Atlanta **does** have one and the
refinement gates 20.03 points. **Both statements are true of the frame each of us used.** The
reason is a data-retention property of `rosters_weekly`, and it makes one of the two frames a
point-in-time leak.

## The mechanism

The live feature build keeps a skill player only if he matched the **ACT** roster
(`upcoming_slate_features`, final `WHERE … sl.active_gsis_id IS NOT NULL`). A player listed
INA is dropped **before** `find_backup_qbs` runs.

`rosters_weekly` for 2026 Week 2, today:

| player | status |
|---|---|
| Michael Penix Jr. (depth 1) | **INA** |
| Tua Tagovailoa (depth 2) | **INA** |
| Cooper Rush | ACT |
| Jack Strand | ACT |

So a live-path run **today** drops both Penix and Tua, Atlanta has no depth-1 row, and the old
guard skips it — production's reading, exactly.

## Why that frame leaks

**`rosters_weekly` has exactly one pull per week, and it is today's.** Week 1 and Week 2 are
both stamped `2026-09-22 10:02:34`. The daily nflverse job rewrites the season as a full
snapshot; no history is kept.

Game-day inactives are published about 90 minutes before kickoff — after the Saturday build and
after the 05:00 CT nflverse pull that every Sunday build reads. **The INA statuses above did not
exist in the table when Week 2 was built.** A re-run against today's table evaluates the gate
with information from after the games.

**The only pre-lock Week-2 QB frame is the one committed on 2026-09-19**
(`reports/reviews/evidence/2026-09-19-qb-gate-live-frame-input.csv`), where Penix is present at
depth 1, Out — and production's **own** propagation report of that date describes Atlanta
precisely that way: *"Penix Out → Tua is the shallowest non-out QB but Doubtful → team left
alone."*

## What this changes, and what it doesn't

**Unchanged — and this matters most:** the operational decision. Under the pair of refinements
Tua is zeroed on *either* frame, production has decided the pair justifies a rebuild, and I
agree. Nothing here argues against shipping.

**Changed — the evidence for each refinement:**

| claim | measured on | status |
|---|---|---|
| Doubtful refinement alone is a no-op | post-game frame | **not point-in-time valid** |
| gate totals 38 QBs / 304.1 → 42 / 342.4 | post-game frame | **not point-in-time valid** |
| depth-1 promotion: 4 of 4 correct, 93.7% precision | post-game frame | **not point-in-time valid** |
| Doubtful refinement gates Tua + Strand, 20.03 pts | pre-lock frame (`4eefbf43`) | valid |
| gate precision 89.6%, 28:1 on points | pre-lock frame (`e86f12a6`) | valid |

**The depth-1 promotion's case deserves the sharpest look.** On the pre-lock frame, **0 of 30
teams lack a depth-1 row**. On the post-game frame, 3 of 26 do. **The "3 teams ungated, 8.5% of
the pool" gap may be substantially created by the look-ahead itself** — post-game INA statuses
removing depth-1 QBs who were present at build time. The rule is still sound as logic (if a
depth-1 QB really is absent from a live frame, promoting the shallowest present is right), but
**its measured benefit came from a frame the live build will not see**, and live it may rarely
fire.

**Why the live build looks like the pre-lock frame:** the T-70 rebuild at 10:50 CT reads the
05:00 CT nflverse pull, which predates game-day inactives. So on Sunday, Out and Doubtful QBs will
generally still be ACT and present — which is exactly the situation where the **Doubtful**
refinement acts and the **depth-1 promotion** does not.

## Logged

Row added to README's data deficiency log, per `CLAUDE.md`: `rosters_weekly` keeps no pull
history, so retrospective runs of roster-dependent logic leak post-game information. Suggested
fix recorded there — append snapshots with their `nflverse_pulled_at` rather than replace.

**Scope check, now done — no training-side leak.** `fantasy_points_alignment_weekly.py:300`
and `fantasy_points_route_weekly.py:319` read `rosters_weekly` as
`SELECT DISTINCT season, gsis_id, full_name, position, team … WHERE week <= @target_week` — an
identity crosswalk. **Neither reads `status`**, so post-game inactives cannot enter a feature
through them. The leak is confined to *retrospective evaluation* of roster-dependent logic.

One minor residual, not a status leak: because only the latest snapshot exists, `team` for a past
week is the player's team **today**, so a player traded after week W is mapped to his new team for
week W. That affects crosswalk accuracy for traded players only, and is covered by the same fix
(keep snapshot history).
