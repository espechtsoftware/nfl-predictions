# Preregistration: does DraftKings' opponent rank (OPRK) add anything to Fantasy Points' projection? Week 5, one week (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** by the laptop, before any Week-5 outcome of the main slate exists (Thursday's TB–DAL game is not on the main
slate). The lab reviewer reviews and freezes it. **One week, descriptive, decides nothing.**

## 1. Why
- **The operator, 10-10 afternoon (the laptop's session, verbatim):** "Can we do a quick study using the DK rankings that we have (which
  I believe is only one week so probably not great yet) and see if it is accurate at all for projecting?  With that a paper study would be
  good." Study list rows 8 (his 10-04 request: "let's look at DraftKings opposing rankings and how well those predict the outcome of the
  game") and 106.
- **What exists:** DK's OPRK only from Week 5 (pre-lock captures; DK rewrites past weeks after the games). Our own matchup measure
  (opponent DK points allowed to the position), 2023–25 out of sample: odds 1.07 per sd for a big game
  (`reports/2026-10-07-why-we-missed-the-winners-players.md` §3.0). An earlier one-slate check (Week 3): OPRK vs our residual −0.05 to −0.14.
- **The paper book** (study 38 amendment 6z6, MIXT_QA0_OPRKBLOCK8) is the separate, real-field test of USING the rank; this read asks only
  whether the rank predicts what FP's projection misses.

## 2. Data (all fixed now)
- **OPRK:** the last `nfl_raw.dk_draftable_attributes` capture of group 154468 strictly before lock (`--lock-utc 2026-10-11T17:00:00Z`),
  attr_id −2, sort_value (1 = the toughest defense vs the position, 32 = the easiest). Sunday's ~10:35 CT capture is planned.
- **The projection:** Fantasy Points' last Main-slate (slate 154468) capture strictly before lock.
- **The outcome:** DK's own FPTS (`nfl_raw.contest_ownership`, Week 5, max over contests per name; names that repeat are dropped).
- **Our DvP:** the opponent's `<pos>_fp_allowed_adj_l6` from `nfl_features.player_week_inference` (Week 5), higher = easier.
- **Players:** QB / RB / WR / TE with an OPRK, an FP projection ≥ 3 and a realized score. The residual = realized − FP projection.

## 3. The read (the reader `reports/2026-10-10-oprk/oprk_accuracy_reader.py`, sha256 `4782fcb87d67f460d988e0e777dd22d684d8574c9467ec975d15228a5a041ad4`)
- Per position: n; Spearman(OPRK, residual) and Spearman(our DvP, residual), each with a 95% bootstrap interval resampling GAMES (team-game
  clusters; B 2,000; seed 20261010).
- All positions together: the mean residual and the 20+ / 30+ point rates by OPRK band (1–11 tough, 12–21 mid, 22–32 easy).
- **Interpretation, fixed now:** a positive Spearman means DK's easier matchups beat FP's projection. With about 20–60 players per
  position from one week, an interval that excludes 0 would be a lead for the weekly line (study 8), not a finding; an interval that
  includes 0 is "no evidence yet". Nothing is adopted from this read. It is re-run each week as the captures accumulate.

## 4. Run
Monday 10-12, after the Week-5 standings load: `python reports/2026-10-10-oprk/oprk_accuracy_reader.py --season 2026 --week 5 --group 154468
--lock-utc 2026-10-11T17:00:00Z`; the output is pasted verbatim under §5 and the lab reviewer re-runs it. Before outcomes the reader
refuses ("an input is empty: no read"; checked 10-10 against the 14:31 capture: 587 OPRK, 571 FP rows, 0 realized).
**The outcome path, exercised 10-10 15:00 CDT on SYNTHETIC outcomes** (fake FPTS = FP + N(0, 6) on W5's real inputs, mechanics only;
the lab reviewer's rule 1): exit 0; every line printed (4 position rows with both Spearmans and their intervals, the 3-band table;
156 players). No real outcome was read.

## 5. Result
(Monday.)
