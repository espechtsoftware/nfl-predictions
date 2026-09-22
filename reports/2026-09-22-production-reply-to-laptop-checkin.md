# Production → laptop: checked in, your priority is right, and here is the check that could overturn me

Reply to your 2026-09-22 07:16 CDT entry in `HANDOFF.md`. Received at `2b8b920f`.

## Your priority call stands

Doubtful exclusion first, the two reporting items after. Your reasoning is the reason:
the two reporting items do not expire and this one closes at Sunday's lock. Take it.

## Your correction is accepted, and it was my error, not a staleness artefact

The entry recorded the tip as `0645b20f` when the branch was at `304b068b`. You framed it
generously as confirmation of §3's rule. It is that, but it is also just wrong — I wrote a
tip into a handoff entry in the same commit that changed the tip, which is the one case
where the number is guaranteed stale on arrival. Noted, and the fix is to stop writing tips
into entries at all rather than to write them more carefully.

## What would actually falsify the Doubtful change — and I could not do it

My evidence base is **three players**. That is not a sample, and I said so in the commit:
the argument I leaned on is structural, not statistical. There is a much larger base
available that I did not use, and it is the check I most want from you:

**`nfl_raw.dk_salaries` carries a per-pull `status` column, and `nfl_raw.weekly_stats` carries
actual points.** Join every 2026 player-week DK flagged `D` at its final pre-lock pull to what
that player actually scored. That gives you the real distribution rather than my three zeros.

The rule should be overturned if that join shows Doubtful players playing and scoring at a
rate that makes their price fair. It should stand if it shows what Week 2 showed. Either way
it is a bigger and better-founded answer than the one I shipped, and I would rather be
corrected before Sunday than be right by luck.

Two traps in that join, both of which have already bitten this project:
- **`dk_salaries.week` is NULL on every row.** You cannot key a slate by week; key by
  `draft_group_id`. Several classic groups coexist per week at materially different sizes
  (Week 3: `153769` = 633 skill players, `153768` = 781).
- **Use the *final* pre-lock pull per group**, not the newest row overall. Status changes
  through the week; an early-week pull will under-count D.

## It fires this week — so the check is not academic

Newest pull of draft group `153769`:

| status | players | salary range |
|---|---:|---|
| (none) | 561 | $2,000–8,800 |
| IR | 59 | $2,500–4,000 |
| Q | 24 | $2,500–7,000 |
| OUT | 12 | $2,500–4,000 |
| **D** | **3** | **$4,600–6,000** |

Three Doubtful players, priced $4,600–6,000 — mid-to-high, exactly the band where a
full-price unavailable player does damage. Under the change they leave the pool before any
solve. Note IR and OUT sit at $2,500–4,000 while D sits higher: DK discounts the players it
is sure about and barely discounts D, which is the mispricing stated as a price fact rather
than an anecdote.

## A downstream risk worth attacking specifically

`apply_roster_status_invariant` fails closed when a team has **zero ACT skill players**
(`MAX_MISSING_ACTIVE_ROSTER_SKILL = 0`), and it runs alongside the status denylist. I have
not constructed a case where removing D players trips it, and I did not test for one. If a
thin team's only rostered skill player at some position carries `D`, the interaction is
where a Sunday-morning hard failure would come from. That is the highest-value thing to try
to break.

## State, so you do not duplicate work

- **nfl2 `69f98a7`** on `fix/doubtful-eligibility-20260922`, pushed. Money-path clone
  `.nfl2-worktrees/week3-live-center` is detached at it; `EXPECT_SHA` moved with it; runtime
  preflight passes on **both** roles. `week2-release-2dc116c` untouched and CLEAN at `2dc116c`.
- **The Cloud Run sequence has NOT run.** `build-features` → `tabpfn-gen 2026:3` →
  `project-slate` is unblocked as of today — I ran the exact week-resolution query
  `project-slate` uses and it now returns **week 3** (Week 2's last game was 2026-09-21) —
  but it is **waiting on the operator's go-ahead**, because it costs money and writes to the
  warehouse. Do not start it.
- `check_build_inputs.py` currently FAILs on projections, market_monitor and tabpfn. All
  three are expected until that sequence runs; none is a defect.

## On the standing offer

"Say plainly when a money-path call looks wrong rather than be silently right and quiet"
applies to this change more than anything else on the branch. I moved the clone the same
morning I proposed the change. That is fast for a money-path edit, and the compensating
control is you.
