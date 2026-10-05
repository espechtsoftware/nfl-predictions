# O-32 correction protocol: re-running six analyses without inactive players

2026-10-05. **FROZEN** by the commit that adds this file, before any re-run outcome exists. The design is the
reviewer's (2026-10-05). It covers the six analyses registered as `reports/OPEN-DEFECTS.md` O-32.

## The defect

Replay panels (`nfl_predictions.slate_player_features`) keep players who did not play with `actual` = 0, and the
table has no `was_active` column. The six analyses below scored the projection against outcomes at the player level
with those rows included. Each inactive row is a miss of about −projection that no pre-lock signal of on-field output
explains, so a real signal is diluted toward the null.

## (a) The single repair

One shared helper, `src/nfl_dfs/analysis/game_day_active.py`, applied identically to all six:
- **Keep** a target row only if `nfl_raw.rosters_weekly` has game-day status ACT for (season, week, gsis_id). That is
  `LOGICAL_OR(status = 'ACT')` over REG rows, so a player traded that week can carry two rows.
- **Drop** a row with no roster row as well.
- The logic is the frozen study 22a reader's (deviation note 1); the reader itself is not changed.
- Game-day status is announced about 90 minutes before kickoff, so the filter is point-in-time for a T-70 build.

Each analysis gets a `game_day_active` switch, OFF by default, so the original runs stay reproducible. The correction
re-run turns it on. Each report records the helper's audit: rows in, kept, dropped as not ACT, and dropped for no
roster row.

## (b) Everything else unchanged

For each study, these stay exactly as frozen:
- the frozen panel id and source-provenance checks;
- the features, folds and model;
- the gate and its thresholds, and the disposition logic.

The repair is applied to the target rows right after they are loaded, before any feature attachment, and in no other
place.

## (c) Order

1. `analysis/fantasy_points_defense_proe.py` first: Thursday's co-run reads the defence re-test arm.
2. `analysis/fantasy_points_qb_shell.py`
3. `analysis/market_tail_disagreement.py`
4. `analysis/ngs_receiver_tail.py`
5. `analysis/pass_participation.py`
6. `scripts/market_movement_eval.py`. It has no gate (Addendum 96 read it as NULL), so its correlations are reported
   beside the original output.

## (d) Reporting

Both dispositions are reported side by side as one system-study correction addendum, whatever they are. Each row
carries:
- the original disposition and the corrected one;
- the helper audit counts;
- the run's code commit;
- the output directory (`reports/o32-correction-runs/<study>/`).

## (e) What a flip can do

- **FAIL → PASS** reopens a CANDIDATE only. These outcomes have been seen for two months, so a flipped gate needs a
  prospective or fresh-bank confirmation and its own adoption package before anything changes.
- **PASS → FAIL** (only `pass_participation` can flip this way) is recorded, and the Route Share gate's motivation is
  noted. Nothing more: the Route Share gate stands on its own prospective record.
- **No change** is recorded as such.

## Adopted levers (the reviewer's check, 2026-10-05)

No adopted production lever rests on an in-class measure:
- `BLEND_W` 0.45 was fit 07-26 on played-only rows.
- `DEFAULT_WIDEN` was fit 07-24 on played-only rows.
- TabPFN L23/L23b target ownership, not points; L24 scores tickets.
- The `tabpfn_*_final_served` family filters `was_active`.
- The 08-01 feature adoptions predate the salary spine (they are under the O-22 audit separately).
- The one in-class verdict tied to an action is `pass_participation`'s support for the paid route trial. Dilution
  biases toward the null, so that support is if anything conservative.

## Mechanics

- Re-runs execute on the laptop, one at a time, never in a build window. The originals' Cloud Run wrappers refuse a
  second execution by design, and no heavy Cloud Run is used.
- The command is `nfl-dfs <analysis subcommand> --game-day-active`, with output captured under the run directory.
- The helper is unit-tested offline: ACT kept, non-ACT and no-roster-row dropped, the audit counts, and the switch's
  default leaving the rows byte-identical.
