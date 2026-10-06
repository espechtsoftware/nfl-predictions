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
1. The shape: **MIXT** (the winners' mix + the term; his preference, study 31) or CT (Week 4's setup, the safe alternative).
2. FP projections as the projection source (decided in principle).
3. FP + props: the paired paper check (recommended) or a trial now.
4. The ownership term: ON at 0.20 on either shape (study 31 reversed study 29; his choice).
5. Dealing stays head (his pins require it; Rev3 = super-satellites on rows 1–26).

## Friday after his yes (laptop; the reviewer has approved each branch)
1. Merge into integration, in this order:
   1. `production/main-mix-20261006` @ `ddd470ed` (MIX / WS / FP source / spares / fallbacks): needed for FP
      projections whatever the shape;
   2. `production/o35-plan-weights-pins-20261006` @ `ce7ba02b` (pin-aware MIX weights): needed only for MIX;
   3. `production/vet-cell-order-20261006` @ `030db347` (O-36: vet_book keeps each MIX cell on its own positions;
      mix_dealt_shares counts replacements by shape): needed only for MIX (approved);
   4. `production/fp-gap-flag-20261006` @ `645bddc0` (the O-22 guard: book players without an FP projection are
      printed, recorded and tagged in vetting, `2d84b96e` approved; plus each week's replacement sources counted, with
      the no-term control rows named, `645bddc0`, for re-approval);
   5. `production/pins-extend-book-20261006` @ `da399bdb` (a pin may add rows without gaps): needed for his Rev3
      plan (super-satellites on rows 1–26; K 22 → 26, caps 13 / 6; approved);
   6. `production/linestar-retire-20261006` @ `b20628fc` (no LineStar capture in the build or at arming).
   Then install Rev3 (`~/private/week5-plan/rev3-26/contests.json`, sha `8625de0e…`) as `~/week5-sunday/contests.json`,
   keeping Rev2 beside it as `contests.json.rev2-94cc61a8` (unmerged production code refuses Rev3's pins, fail-closed).
2. A follow-up for review: the arming banner prints `ENTER_LAYOUT`.
3. The money-path test modules green with `GCP_PROJECT` unset; `check_week_runtime` in the armed env: head / the plan's rows
   / no LayoutError on the installed plan (Rev3: head / 26 rows / caps 13 / 6; Rev2 would be 22).
4. The production checkout `~/projects/nfl-predictions` fast-forwarded to the merged head, clean.
5. **A FULL REHEARSAL at Week-5 size, archive mode (the reviewer, the K-dependence lesson):** the union on the W4 T-70
   frame with the installed contests (Rev3) and his chosen arm line (e.g. MIXT: MIX + FP + the term at 0.20), `--mix-spares 15`; then vet_book
   and vet_replace with `--test-exclude-dk` of a player in >= 8 entries; then `enter_layout write`. Print and check: (1)
   the dealt cell shares by ENTRIES near A1 .30 / A2 .14 / B .28 / C .28 (pins weighted, O-35 live); (2) the 8 pinned
   contests' ENTER files carry rows 1-5 exactly as pinned; (3) 15 spares in the corpus; (4) the replacement uses
   in-shape spares or the flagged house fallback, and no row ships with the excluded player; (5) audit_build_levers
   PASS. NOT-PUBLISHABLE (test flags). The last proof before the money path runs it. The 10-06 preview found O-36
   (check 1 failed by entries until the vet-cell-order fix); its re-run with the fix passed all five.
6. The lab pin for MIX / WS: `EXPECT_SHA f69598ba…` with `CLONE ~/projects/.nfl2-worktrees/week5-live-center`
   (`optimize(second_game_pair, qb_game_max)`); the house shape could stay on `32cdb61`.

## Saturday 10-10 (the laptop arms; fail-stop script, ask only if blocked)
- A host-local Week-5 arm script from `~/.cache/laptop-agent/w4_arm_saturday.sh`: GROUP 154468; the inputs (sets, lag +
  gate, TabPFN lags); **no LineStar step**; the arm line per his Friday choices, e.g. `UNION_MAIN=mix
  UNION_MIX_PORTFOLIO=mix UNION_PROJ_SOURCE=fp UNION_MAIN_OWN_TILT=0.20 UNION_MAIN_OWN_PREDICTOR=fp` (MIXT: study 31
  recommends the term ON on either shape; his choice) and `EXPECT_SHA` / `CLONE` above; plain MIX without the term is
  not to be armed (study 31); the expected timer count includes the FP projections capture (11, or 9 when
  armed late).
- The FP projections capture runs right after arming; Sunday's runs at 10:40 CT, before the 10:50 T-70 build.

## Sunday 10-11
- The T-70 build on the post-10:30 salary pull; FP projections (refusal → ours, loud); the ownership chain FP → LAG
  0.10 → none; WS/MIX spares and the house fallback for late scratches (`ddd470ed`).
- Any manual relayout passes `ENTER_LAYOUT=head` (O-34).

## Monday 10-12
- `weekly_projection_accuracy.py` (ours / FP / blend) and `weekly_fp_props_check.py` (FP vs FP + props), then `pool`.
- Settlement; the entered book vs the paper rebuild of today's house shape on the same slate.
