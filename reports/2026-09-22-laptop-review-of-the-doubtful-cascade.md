# Review: the Doubtful next-man-up cascade (`aaf6058f`, deployed off) — verified; its value sits in the early-slate T-70 window

Reviewing production's `edfe84b4` and branch `production/week3-qbgate-on-cf630a68-20260922` @ `aaf6058f`.

## Chain of custody — verified

| check | result |
|---|---|
| diff `dfefbc55..aaf6058f` | one commit; `find_out_players` plus tests plus walk-forward script; nothing else touched |
| default | `CASCADE_DOUBTFUL` unset or "0" → mask unchanged; QBs excluded (stay with `find_backup_qbs`) |
| `DOUBTFUL_STATUSES` / `_col` | module-level (lines 213/217), resolved at call time — fine |
| tests | `tests/test_cascade_adjust.py` 22 passed at `aaf6058f` (laptop, worktree) |
| build | `7be05408…` SUCCESS, `_CODE_SHA=aaf6058f…`, digest `sha256:3dac541c…c929` |
| project-slate | image `@sha256:3dac541c…c929`; env `Q_HAIRCUT=0.80`, `BLEND_MODEL_WEIGHT=0.45`, `MODEL_ENSEMBLE=1`, `tail_k1`; **no `CASCADE_DOUBTFUL`** |

## "On the Week-2 frame it triggers exactly Flowers and Bowers" — confirmed independently

Every non-QB DK status `D` in `dk_salaries` pulls between 09-17 and Sunday lock: Bowers (LV),
Flowers (BAL), Whittington (LAR), Demarcus Robinson (SF). Whittington's game was Monday night (off
the main slate), and Robinson's `D` appears only from 09-21 against his **Week-3** game. That leaves
exactly Flowers and Bowers.

## Where the flag adds value: timing

The cascade already fires for `OUT`. `CASCADE_DOUBTFUL` changes a build only when a player is still
`D`, not yet `OUT`, at the pull the build uses:

| player | D window (CT) | OUT from (CT) | kickoff (CT) | at main-slate T-70 (10:50 CT Sun) |
|---|---|---|---|---|
| Zay Flowers | Thu 14:37 → Sat 14:43 | **Sat 15:44** | Sun 12:00 | already OUT → existing cascade fires |
| Brock Bowers | Fri 15:37 → Sun 12:49 | Sun 13:50 | Sun 15:05 | **still D → only the new flag fires** |

So for Week 2, at the T-70 rebuild, the flag's incremental effect is **Bowers alone**. Flowers
matters only for builds made before Saturday afternoon. This is the usual pattern for late-game
Doubtfuls: teams often downgrade D → OUT only at the ~90-minute inactives, which falls after the
main-slate T-70 for 3:05/3:25 games. That is exactly where this flag earns its keep.

## Assessment

- The evidence direction is sound: residual +1.04 past a Doubtful starter vs −0.02 past an Out
  starter. The walk-forward is season-split, as the law requires. The per-season −0.07 / +1.49 /
  +1.53 figures fail "at most one negative" only if −0.07 counts as a negative; it is ~0.
- One risk to name, not a blocker: the cascade redistributes the **full** vacated usage. Doubtful
  players play ~3% (panel 2.8%; Week 2 0 of 13), so treating Doubtful as fully absent over-shoots by
  at most ~3% of the vacated share. That is negligible.
- No double count with the vacated-share **features**: they count only Out, so for a Doubtful
  starter the cascade is the only adjustment.
- Recommendation to the operator: **enable for Week 3** (`CASCADE_DOUBTFUL=1` on project-slate).
  It is consistent with the Doubtful exclusion the pool already applies (nfl2 `69f98a7`): the pool
  already treats D as absent, and this makes the teammates' projections agree.
