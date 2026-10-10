# Preregistration: study 116, a receptions floor for running backs, on his armed Week-5 book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's
(its calls of 10-10, about 10:25). The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks
and reproduces. **A pick goes to study 116b** (the fresh-draw check), whose preregistration is committed before this study's
READ. **The operator's order (10-10, via the laptop): "Hold 114 until after"** — study 114 stays frozen and unrun until 116
(and 116b) read.
- **Banks and seed (the laptop's reservation; the full-set check: CLEAN):** **4008–4019** (set A 4008–4013, set B 4014–4019;
  sims bases 4058–4069, fields 4708–4719); the reader's bootstrap seed **20261161**.

## 1. Why
- **The operator, 10-10, in the laptop's session (verbatim; study list row 97):** "Let's try another experiment where we have a
  minimum number of receptions for a running back."
- **Where the idea came from — IN-SAMPLE, stated plainly.** After study 112's READ, at his request ("Im surprised with the
  results of the number of carries. Can you double check that"), the outside reviewer looked at study 112's scored banks: the
  running backs the 13-carry floor removed from LIVE's book averaged 10.6 carries and 4.2 targets a game and scored 14.3 real
  DraftKings points (20+ points 25.7% of the time); their replacements averaged 15.5 carries and 3.0 targets and scored 13.1
  (18.0%). **That was seen in the real outcomes of these same 36 slates.** A receptions floor read on them is therefore partly
  in-sample: study 116b's fresh banks re-draw the opponents and simulations, not the outcomes. The unused 2022 slates are not
  available in this harness (no pre-lock ownership predictions for 2022).
- **So a pass reads "consistent with the idea on the same slates", never "out-of-sample".**
- **His decision, before this study is read (10-10, in the laptop's session, verbatim):** asked about the paper-arm route,
  "Please try it now and only of successful include it this week"; asked what "successful" means, "116 and re-check pass
  (Recommended)". **So: if study 116 picks a dose AND study 116b confirms it, the floor goes into his real Week-5 entries**
  (the laptop builds the default-off production switch to this file's measure); there is no paper arm. If either fails,
  nothing changes. He made this decision knowing the in-sample caveat above (the laptop's plain-words relay).
- **The pass-catcher reason is an argument, not a measurement:** DraftKings pays a point per catch, so a back who catches
  passes can outscore a heavier-carry back.
- **The prior: NO DIFFERENCE, leaning negative.** Every floor tested today read worse on both draws: the projection floor
  (study 106, −2.7), the carries floor (study 112's RUSH 13, −4.6, an interval clear of zero), pass attempts (−2.7), targets
  (−2.8). A floor removes players; the big wins draw on cheap ones.

## 2. Arms (`experiments/s116_rec_floor.py`)
**Study 112's frozen module exactly** (`s112_usage_floors.py` `16bbe046…`, sha-asserted; it pins studies 106, 95 and 97);
`run()` = 112's `run()` with four listed edits (a test asserts it). **Every arm is his armed Week-5 book** (the package, te1 /
low1, the cheap +2 block, ONECATCH and the adopted FAVHI, its pairs on each arm's pool).

**One change per arm: a receptions floor for running backs, applied as a pool filter** before the ownership caps, the row-rule
sets, the cheap block's term and the FAVHI pairs (112's `usage_pool` = 106's `arm_pool` pattern = production's `excl`).
- **The measure:** a running back's **receptions per game** = the mean over his up to 4 prior regular-season games **of the
  same season**, strictly before the slate's week (nflverse weekly `receptions`; study 112's PASS path and window). A player
  with no prior game this season (Week 1 always) is **kept** and counted. Other positions and DSTs are never removed.
- **How production would read it:** there is no `receptions_l4` in the usage table; production would take `receptions` from
  `nfl_features.player_week_actuals` over the same window. **The two sources agree exactly** where both have a stat line:
  3,009 of 3,009 running-back weeks of 2023–24 (the outside reviewer, 10-10), and every RB-week of 2025 (1,575) and 2026
  Weeks 1–5 (370) (the laptop, 10-10).
  - **The equivalence condition:** `player_week_actuals` also carries salary-listed inactive rows with receptions 0
    (`has_stat_line` false). A production mean must **skip those rows** (as feature 015 does for DK points), or a missed game
    counts as zero catches. nflverse weekly has no such rows, so the harness's window counts games with a stat line only.
- **LIVE** — his armed book.
- **REC** — RBs with receptions per game **below X_REC** leave.
- **REC_LOW** — RBs with receptions per game **below X_REC_LOW** leave.

## 3. THE THRESHOLD RULE (fixed now, BEFORE any census is run; the lab reviewer's)
- **REC:** the round value nearest the placeholder **2.0**, in steps of **0.5**, such that LIVE's book rows touched average
  **between 8 and 15 of 26** per slate-bank on bank 1406 (the 36 slates). Ties in distance go to the lower value.
- **REC_LOW:** the **largest** value below REC's choice, in the same steps, with LIVE's rows touched in **[3, 8)**.
- A row is touched when it holds a running back the floor removes.
- **AND, at its threshold, each arm's own build passes:** the cheap block never empty (production refuses an empty block);
  ONECATCH drops ≤ 5% of B / C book solves; the RB-mate slots complete (4 per book). **An arm with no threshold in range, or
  failing its checks, is dropped** (recorded).
- **The procedure:** the census's THRESHOLD SCAN reads only LIVE's book composition (each LIVE row's lowest RB receptions
  value), outcome-blind, and prints both choices. Where a choice differs from the run's placeholder, the module is set to it
  and the smoke re-run; the lab reviewer checks the census lines and the numbers before the freeze; this file records them.

## 4. The read (the reader `scripts/s116_report.py`)
- **Study 112's reader with six listed edits, relabelled** (a test asserts them); study 63's statistics; two draws (the same
  past slates, two random opponent sets) and pooled; two-sided 0.95, B 20,000.
- **Per arm − LIVE:** P(≥ 1 big seat), its guards and verdict; **his rule's line** (better on both draws AND the pooled expected
  big seats ratio ≥ 0.80); the mean best real lineup points and P(best ≥ 200), printed.
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick goes to study 116b.**
- **Multiplicity:** two doses on the same 36 slates as studies 89–115.
- **What a pass would mean (pre-stated):** "consistent with the idea on the same slates" (§1). **His decision (§1): a pick
  that study 116b confirms goes into his Week-5 entries.** The production switch (default off; the `excl` pool filter on a
  pre-lock receptions file, its mean over stat-line games only, §2) is built by the laptop to this file's measure, with its
  tests, the Week-4 check and study 38's classification before the arm.

## 5. Honest limits and the census
- **The harness builds on its own simulated means;** his book uses Fantasy Points' projections. The floor removes the same
  players in both (the usage data is shared), but which lineups result differs.
- **The census, per arm (outcome-blind, bank 1406):** the pool; the RBs dropped, **by salary band (under $5,000; $5,000–6,900;
  $7,000+) with their mean prior targets per game**; the cheap players left and given the term; the TE / low-owned pools;
  LIVE's rows touched; the FAVHI pairs per slate (mean and minimum) and the RB-mate floor's fallbacks; the spares built; the
  coverage; the threshold scan; ONECATCH; rows shared with LIVE and dealt identity; LIVE == study 97's RBMATE4_FAVHI
  (`--ref97`). Per-slate fields stay outside the blocks the reader compares.

## 6. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke and the census (the unit tests, the mechanics smoke 2023 W3
  / 2023 W11 / 2024 W10, the census with its threshold scan, the full path: reader exit and line count only).
- **The smoke at the placeholders (DONE 10-10, 10:32:43–10:34:37 CDT, in the gap the lab reviewer named after the laptop's
  study-114 ack; bank 1406; 2024 W10, 2023 W11, 2023 W3; PYTHONHASHSEED=0; code `1d58fbbc`; `results_bank1406.jsonl`
  `3dfe436e…`):**
  - the unit tests 12 passed;
  - every arm 26 book rows within the package's caps; row rules 78 of 78 ruled, none infeasible; RB-mate slots 12 of 12 and
    ONECATCH 42 of 42, none dropped, every arm; spares 15 of 15; the cheap block never empty (86 given the term in every arm);
    **LIVE identical to study 97's RBMATE4_FAVHI on 3 of 3**; coverage 316.7 frame rows with a receptions value per slate-bank;
  - LIVE's rows touched: REC (< 2.0) 9.0 (min 4), REC_LOW (< 1.5) 4.7 (min 2); dealt identical to LIVE 0.000 for both;
  - **the RBs dropped per slate-bank:** REC 33.3 (under $5,000 24.3 / $5,000–6,900 8.7 / $7,000+ 0.3; their prior targets 1.11
    a game); REC_LOW 24.3 (18.0 / 6.0 / 0.3; 0.79 targets). FAVHI pairs left: REC 7.7 (min 5), REC_LOW 11.0 (min 7);
  - **the 3-slate scan** (a preview; the binding census on the 36 slates decides): 1.5 → 4.7 rows, 2.0 → 9.0, 2.5 → 13.7, 3.0
    → 20.0; the rule picks REC 2.0 and REC_LOW 1.5 here;
  - the full path: the reader exited 0 (41 lines; 52 two-draw). Only the census, the exit codes and the line counts were
    read.
- **The chosen thresholds: REC 2.0, REC_LOW 1.5 — the placeholders, confirmed by the lab reviewer's binding census** (10-10,
  10:35:14–10:37:42 CDT; bank 1406, the 36 slates, lab `d2e0d237`, `CENSUS` `d8d0cbe2…`): LIVE's rows touched 1.5 → 4.9, 2.0 →
  8.3, 2.5 → 14.9 (REC: 2.0 is in [8, 15] and nearest 2.0; REC_LOW: 1.5 is the largest value below it in [3, 8)); 0 fallbacks;
  LIVE == study 97's RBMATE4_FAVHI on 36 of 36; RBs dropped 32.7 / 25.6 per slate-bank, mostly under $5,000, prior targets 1.12
  / 0.87; FAVHI pairs at minimum 1 / 2 on a slate, the RB-mate floor re-solved without them in 4 / 2 of 144 slots. **No
  re-smoke was needed:** the code does not change, so the smoke at the placeholders above is the smoke at the choices.
- **Code:** nfl2 `production/s116-rec-floor-20261010` @ `1d58fbbc` (off study 112's `262be08b`, whose module is the frozen
  `16bbe046`):
  - `experiments/s116_rec_floor.py` `429b7ee5…` (pins s112 `16bbe046…`)
  - `scripts/s116_drive.py` `0d80759b…`
  - `scripts/s116_census.py` `2d585066…`
  - **`scripts/s116_report.py` (the reader) `29acee51…`** (seed 20261161)
  - `tests/test_s116_rec_floor.py` `e56aa896…` (12)
  - The rule's choices equal the placeholders, so the code line stands.
