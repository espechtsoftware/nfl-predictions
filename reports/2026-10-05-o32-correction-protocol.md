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

## Amendment 1 (2026-10-05, before any re-run): the reproduction leg (reviewer's condition for local runs)

The repair is approved and merged at `1b1d50d4`. The originals ran on immutable Cloud Run images; the corrections run
locally (no heavy Cloud Run). The image's immutability is therefore replaced by a measured reproduction.

- **Two local legs per study,** from the same reviewed commit, by `scripts/o32_correction_run.sh <study>`:
  `game_day_active` OFF (**uncorrected**) and ON (**corrected**).
- **The runner records** the commit, the panel id and the environment (python, pandas, numpy, scikit-learn, scipy,
  lightgbm, google-cloud-bigquery, nflreadpy) in `reports/o32-correction-runs/<study>/environment.txt`. It refuses a
  dirty `src/` or `scripts/`, and refuses a second correction of the same study.
- **Three columns are reported:** original (Cloud image) | local uncorrected | local corrected. The correction's
  effect is local-uncorrected against local-corrected, so code or environment drift since August cancels out.
- **The reproduction gate.** If the local uncorrected leg does not reproduce the original disposition and key numbers
  (within float tolerance), that study's correction STOPS. The drift is disclosed and the study is recorded as
  "environment changed since the verdict" before anything is said about the filter.

**Implications of filtering right after load, named per module** (the reviewer's request). No module derives a
history from the panel's own `actual`: the priors come from box-score weekly (defence PROE), the FP shell table (QB
shell), prop lines (market tail), NGS (NGS receiver) and pbp participation (pass participation). The filter does,
however, change each fitted model's TRAINING rows, as well as the evaluation rows:
- market tail trains on season 2024 rows;
- NGS receiver and pass participation train on walk-forward folds;
- defence PROE and QB shell fit nothing: they correlate and score.

Fewer rows can also bind a gate's support condition (for example NGS "≥ 1,000 rows each fold", defence PROE "≥ 90%
coverage each fold"). A gate that fails on support after the filter is reported as such, never as a signal verdict.

## Amendment 2 (2026-10-05, before any re-run): the comparison gate; market movement is out of class

- **The reproduction decision reads a WHITELIST per study** (`scripts/o32_compare.py`, reviewer): the disposition, the
  gate booleans and the gate's numeric statistics (control and treatment Brier and MAE, and rows; for market tail, the
  held-out overall statistics and the train/held-out row counts). Every other field (source audits, retrieval times,
  run ids) is printed as context and never decides.
- **Leg identity.** The corrected leg must carry `game_day_active` (the rule string, rows_kept > 0) and the uncorrected
  leg must not. Otherwise the comparison exits 4 and nothing is concluded.
- **`scripts/market_movement_eval.py` (Addendum 96) is OUT of class.** Its panel `20260805-hf5` predates the 08-08
  salary spine: of its 13,968 player-weeks for 2023–25, 0 are non-ACT on game day; 54 have no roster row.
  - The evidence is a count of non-ACT rows by roster status, the same mechanical check as deviation note 1. No
    correlation was computed.
  - It has no correction leg, and O-32's in-class list is five.

## Amendment 3 (2026-10-05, before the defence-PROE correction's results): read the frozen import only

**Found.** The first defence-PROE run (`reports/o32-correction-runs/defense-proe-attempt1/`, commit `680f2212`)
stopped on its uncorrected leg before producing any output: "Defense PROE table provenance is invalid".

**Cause.** `nfl_raw.fantasy_points_defense_proe` still holds the frozen 2022–2025 import intact: 2,174 rows, 4 hashes
and one run, `fantasy-points-defense-proe-2022-2025-v1`, the contract the August Cloud wrapper checked. Since
2026-09-23, however, the weekly vendor run has APPENDED three 2026 runs of 32 rows each. The analysis reads the whole
table and requires a single run id, so it now refuses.

**Repair.** One line, applied to BOTH legs: `run()` reads `WHERE source_run_id = SOURCE_RUN`, the ingest module's
constant `fantasy-points-defense-proe-2022-2025-v1`. The provenance checks (the four expected hashes, one run) are
unchanged. The analysis reads 2022–2025 only by design, so this restores the August input exactly; the reproduction
leg must still match the original.

**Sweep** (frozen-chain rule 4).
- QB shell's source `fantasy_points_qb_shell_l4` holds only its frozen run (4 × 448 rows), and its correction
  reproduced exactly.
- The DraftKings prop lines for 2024–25 have no snapshot after their seasons.
- The NGS and pass-participation analyses download nflverse data live. Revisions there are caught by their
  reproduction legs; there is no table contract to fix in advance.

## Result: QB shell (run 2026-10-05, commit `680f2212`)

**REPRODUCED.** The local uncorrected leg equals the August Cloud report on every whitelisted field.

**CORRECTED: `fp-qb-shell-player-tail-fails` → `fp-qb-shell-player-tail-fails` (unchanged).**
- The filter dropped 1,481 of 3,884 target QB rows (38%; backup QBs listed with 0 points).
- The aggregate went from 2,918 to 1,796 rows; the 20- and 30-point events are unchanged (321 and 61).
- The treatment's Brier-30 is 0.030371 vs the control's 0.030366: still not an improvement.

Full columns: `reports/o32-correction-runs/qb-shell/comparison.txt`.
