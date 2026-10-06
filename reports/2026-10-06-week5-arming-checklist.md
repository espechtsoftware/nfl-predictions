# Week 5: the arming checklist (Tue 10-06 → Sun 10-11)

The laptop, 10-06; the reviewer has seen each item's source. One page of what must happen, in order, so nothing rests on
chat. Private paths stay private (no dollars, no entries here).

## Before Friday (laptop)
| when | item | source |
|---|---|---|
| when FP posts it | the weekly vendor run `nfl-weekly-data run --week 5` (PROE waits for ATL/NO's MNF; Route Share W4 already loaded) — every paid page, SIS included | HANDOFF 10-06 |
| Wed 10-07 | O-3 SIS pass-tail: SIS session check, env check against the CURRENT policy, one outcome-blind dry run per job, then resume the three schedulers (first scheduled run Thu 09:15) | OPEN-DEFECTS O-3 |
| Thu 10-08 | O-25 Route Share companion-v1: one dry run per job (`SHADOW_DRY_RUN=1`) through the launcher lanes; deadline Sat 12:00 | OPEN-DEFECTS O-2 / O-25 |
| Thu | O-27 cbwu-oi: the fix's dry run | OPEN-DEFECTS O-27 |
| Thu | `check_prospective_gates.py --week 5` must pass (no paused graded gate; env = policy) | CLAUDE.md |

## Friday 10-09: the operator's decisions (decision sheet `briefings/2026-week-05/2026-10-05-week5-decision-sheet.md`)
1. The shape: **MIX** (recommended as his preference; study 28), WS, or today's house shape.
2. FP projections as the projection source (decided in principle).
3. FP + props: the paired paper check (recommended) or a trial now.
4. The ownership term on MIX: study 29's read (in progress).
5. Dealing stays head (his Rev2 pins require it).

## Friday after his yes (laptop; the reviewer has approved each branch)
1. Merge into integration, in this order:
   1. `production/main-mix-20261006` @ `ddd470ed` (MIX / WS / FP source / spares / fallbacks): needed for FP
      projections whatever the shape;
   2. `production/o35-plan-weights-pins-20261006` @ `ce7ba02b` (pin-aware MIX weights): needed only for MIX;
   3. `production/linestar-retire-20261006` @ `b20628fc` (no LineStar capture in the build or at arming).
2. A follow-up for review: the arming banner prints `ENTER_LAYOUT`.
3. The money-path test modules green with `GCP_PROJECT` unset; `check_week_runtime` in the armed env: head / 22 rows
   / no LayoutError on Rev2 (`~/week5-sunday/contests.json` sha `94cc61a8…`).
4. The production checkout `~/projects/nfl-predictions` fast-forwarded to the merged head, clean.
5. The lab pin for MIX / WS: `EXPECT_SHA f69598ba…` with `CLONE ~/projects/.nfl2-worktrees/week5-live-center`
   (`optimize(second_game_pair, qb_game_max)`); the house shape could stay on `32cdb61`.

## Saturday 10-10 (the laptop arms; fail-stop script, ask only if blocked)
- A host-local Week-5 arm script from `~/.cache/laptop-agent/w4_arm_saturday.sh`: GROUP 154468; the inputs (sets, lag +
  gate, TabPFN lags); **no LineStar step**; the arm line per his Friday choices, e.g. `UNION_MAIN=mix
  UNION_MIX_PORTFOLIO=mix UNION_PROJ_SOURCE=fp UNION_MAIN_OWN_TILT=0.20 UNION_MAIN_OWN_PREDICTOR=fp` (the term per study
  29) with `EXPECT_SHA` / `CLONE` above; the expected timer count includes the FP projections capture (11, or 9 when
  armed late).
- The FP projections capture runs right after arming; Sunday's runs at 10:40 CT, before the 10:50 T-70 build.

## Sunday 10-11
- The T-70 build on the post-10:30 salary pull; FP projections (refusal → ours, loud); the ownership chain FP → LAG
  0.10 → none; WS/MIX spares and the house fallback for late scratches (`ddd470ed`).
- Any manual relayout passes `ENTER_LAYOUT=head` (O-34).

## Monday 10-12
- `weekly_projection_accuracy.py` (ours / FP / blend) and `weekly_fp_props_check.py` (FP vs FP + props), then `pool`.
- Settlement; the entered book vs the paper rebuild of today's house shape on the same slate.
